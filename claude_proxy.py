import json
import os
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import AsyncIterator

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, PlainTextResponse, StreamingResponse


UPSTREAM_BASE_URL = os.getenv("CLAUDE_PROXY_UPSTREAM_BASE_URL", "https://uuapi.net").rstrip("/")
UPSTREAM_API_KEY = os.getenv("CLAUDE_PROXY_UPSTREAM_API_KEY", "")
UPSTREAM_AUTH_MODE = os.getenv("CLAUDE_PROXY_UPSTREAM_AUTH_MODE", "x-api-key").strip().lower()
LOG_DIR = Path(os.getenv("CLAUDE_PROXY_LOG_DIR", str(Path(__file__).resolve().parent / "logs" / "claude_proxy")))
REQUEST_LOG_PATH = LOG_DIR / "requests.jsonl"
RESPONSE_LOG_PATH = LOG_DIR / "responses.jsonl"
REQUEST_BODY_DIR = LOG_DIR / "request_bodies"
RESPONSE_BODY_DIR = LOG_DIR / "response_bodies"
TIMEOUT = httpx.Timeout(connect=30.0, read=300.0, write=300.0, pool=30.0)
HOP_BY_HOP_HEADERS = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailer",
    "transfer-encoding",
    "upgrade",
    "host",
    "content-length",
}

LOG_DIR.mkdir(parents=True, exist_ok=True)
REQUEST_BODY_DIR.mkdir(parents=True, exist_ok=True)
RESPONSE_BODY_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="Claude Code Transparent Proxy")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def mask_secret(value: str) -> str:
    if not value:
        return value
    if len(value) <= 10:
        return "*" * len(value)
    return f"{value[:6]}...{value[-4:]}"


def normalize_headers(headers: httpx.Headers | dict) -> dict[str, str]:
    normalized = {}
    for key, value in dict(headers).items():
        lowered = key.lower()
        if lowered in {"authorization", "x-api-key"}:
            normalized[key] = mask_secret(value)
        else:
            normalized[key] = value
    return normalized


def build_upstream_headers(request_headers: dict[str, str]) -> dict[str, str]:
    forwarded = {}
    for key, value in request_headers.items():
        lowered = key.lower()
        if lowered in HOP_BY_HOP_HEADERS:
            continue
        forwarded[key] = value

    if UPSTREAM_API_KEY:
        if UPSTREAM_AUTH_MODE == "bearer":
            forwarded["authorization"] = f"Bearer {UPSTREAM_API_KEY}"
            forwarded.pop("x-api-key", None)
        elif UPSTREAM_AUTH_MODE == "x-api-key":
            forwarded["x-api-key"] = UPSTREAM_API_KEY
            forwarded.pop("authorization", None)
        elif UPSTREAM_AUTH_MODE == "both":
            forwarded["authorization"] = f"Bearer {UPSTREAM_API_KEY}"
            forwarded["x-api-key"] = UPSTREAM_API_KEY
        elif UPSTREAM_AUTH_MODE == "passthrough":
            pass
        else:
            forwarded["x-api-key"] = UPSTREAM_API_KEY
            forwarded.pop("authorization", None)

    return forwarded


def append_jsonl(path: Path, payload: dict) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")


def write_bytes(path: Path, content: bytes) -> None:
    with path.open("wb") as handle:
        handle.write(content)


async def stream_and_capture(
    upstream_response: httpx.Response,
    response_id: str,
) -> AsyncIterator[bytes]:
    response_body_path = RESPONSE_BODY_DIR / f"{response_id}.bin"
    captured = 0
    max_capture_bytes = 1024 * 1024
    with response_body_path.open("wb") as handle:
        async for chunk in upstream_response.aiter_bytes():
            if captured < max_capture_bytes:
                slice_end = min(len(chunk), max_capture_bytes - captured)
                handle.write(chunk[:slice_end])
                captured += slice_end
            yield chunk


@app.get("/")
async def root() -> dict:
    return {
        "name": "claude-code-transparent-proxy",
        "upstream_base_url": UPSTREAM_BASE_URL,
        "upstream_auth_mode": UPSTREAM_AUTH_MODE,
        "request_log": str(REQUEST_LOG_PATH),
        "response_log": str(RESPONSE_LOG_PATH),
    }


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "time": utc_now()}


@app.api_route("/{full_path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"])
async def proxy(full_path: str, request: Request):
    started_at = time.perf_counter()
    request_id = str(uuid.uuid4())
    request_body = await request.body()
    request_body_path = REQUEST_BODY_DIR / f"{request_id}.bin"
    write_bytes(request_body_path, request_body)

    incoming_headers = dict(request.headers)
    upstream_headers = build_upstream_headers(incoming_headers)
    url = f"{UPSTREAM_BASE_URL}/{full_path}"
    if request.url.query:
        url = f"{url}?{request.url.query}"

    request_log = {
        "id": request_id,
        "timestamp": utc_now(),
        "method": request.method,
        "path": f"/{full_path}",
        "query": request.url.query,
        "url": url,
        "client": request.client.host if request.client else None,
        "headers": normalize_headers(incoming_headers),
        "forwarded_headers": normalize_headers(upstream_headers),
        "body_file": str(request_body_path),
        "body_size": len(request_body),
    }
    append_jsonl(REQUEST_LOG_PATH, request_log)

    try:
        async with httpx.AsyncClient(timeout=TIMEOUT, follow_redirects=False) as client:
            upstream_request = client.build_request(
                method=request.method,
                url=url,
                headers=upstream_headers,
                content=request_body,
            )
            upstream_response = await client.send(upstream_request, stream=True)

            response_id = request_id
            response_log = {
                "id": response_id,
                "timestamp": utc_now(),
                "status_code": upstream_response.status_code,
                "headers": normalize_headers(upstream_response.headers),
                "content_type": upstream_response.headers.get("content-type"),
                "elapsed_ms": int((time.perf_counter() - started_at) * 1000),
                "request_id": request_id,
                "response_body_file": str(RESPONSE_BODY_DIR / f"{response_id}.bin"),
            }
            append_jsonl(RESPONSE_LOG_PATH, response_log)

            content_type = upstream_response.headers.get("content-type", "")
            response_headers = {
                key: value
                for key, value in upstream_response.headers.items()
                if key.lower() not in HOP_BY_HOP_HEADERS
            }

            if "text/event-stream" in content_type.lower():
                return StreamingResponse(
                    stream_and_capture(upstream_response, response_id),
                    status_code=upstream_response.status_code,
                    headers=response_headers,
                    media_type=content_type,
                )

            response_bytes = await upstream_response.aread()
            write_bytes(RESPONSE_BODY_DIR / f"{response_id}.bin", response_bytes)
            await upstream_response.aclose()
            return PlainTextResponse(
                content=response_bytes.decode("utf-8", errors="replace"),
                status_code=upstream_response.status_code,
                headers=response_headers,
                media_type=content_type or None,
            )
    except httpx.HTTPError as exc:
        error_log = {
            "id": request_id,
            "timestamp": utc_now(),
            "error": str(exc),
            "type": exc.__class__.__name__,
            "elapsed_ms": int((time.perf_counter() - started_at) * 1000),
        }
        append_jsonl(RESPONSE_LOG_PATH, error_log)
        return JSONResponse(status_code=502, content={"error": "upstream_request_failed", "detail": str(exc)})
