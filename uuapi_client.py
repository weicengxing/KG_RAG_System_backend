import json
import os
import uuid
from typing import Any

import httpx


DEFAULT_BASE_URL = os.getenv("UUAPI_BASE_URL", "https://uuapi.net").rstrip("/")
DEFAULT_MODEL = "claude-opus-4-6"
SUPPORTED_MODELS = {"claude-opus-4-6", "claude-sonnet-4-6"}
DEFAULT_BETA = ",".join(
    [
        "claude-code-20250219",
        "context-1m-2025-08-07",
        "interleaved-thinking-2025-05-14",
        "redact-thinking-2026-02-12",
        "context-management-2025-06-27",
        "prompt-caching-scope-2026-01-05",
        "effort-2025-11-24",
    ]
)
DEFAULT_SYSTEM_PROMPT = [
    {
        "type": "text",
        "text": "x-anthropic-billing-header: cc_version=2.1.110.610; cc_entrypoint=cli; cch=00000;",
    },
    {
        "type": "text",
        "text": "You are Claude Code, Anthropic's official CLI for Claude.",
        "cache_control": {"type": "ephemeral"},
    },
]


class UUAPIError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        error_code: str = "uuapi_error",
        content_type: str | None = None,
        response_preview: str | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.error_code = error_code
        self.content_type = content_type
        self.response_preview = response_preview


def resolve_api_key(explicit_api_key: str | None = None) -> str:
    api_key = explicit_api_key or os.getenv("UUAPI_API_KEY") or os.getenv("CLAUDE_PROXY_UPSTREAM_API_KEY", "")
    return api_key.strip()


def normalize_model(model: str | None) -> str:
    if model in SUPPORTED_MODELS:
        return model
    return DEFAULT_MODEL


def build_headers(api_key: str, session_id: str) -> dict[str, str]:
    return {
        "accept": "application/json",
        "anthropic-dangerous-direct-browser-access": "true",
        "anthropic-version": "2023-06-01",
        "anthropic-beta": DEFAULT_BETA,
        "authorization": f"Bearer {api_key}",
        "content-type": "application/json",
        "user-agent": "claude-cli/2.1.110 (external, cli)",
        "x-app": "cli",
        "x-claude-code-session-id": session_id,
        "x-stainless-lang": "js",
        "x-stainless-os": "Windows",
        "x-stainless-arch": "x64",
        "x-stainless-package-version": "0.81.0",
        "x-stainless-runtime": "node",
        "x-stainless-runtime-version": "v25.9.0",
        "x-stainless-retry-count": "0",
        "x-stainless-timeout": "300",
        "accept-language": "*",
        "sec-fetch-mode": "cors",
        "accept-encoding": "gzip, deflate",
    }


def to_claude_message(role: str, text: str) -> dict[str, Any]:
    return {
        "role": role,
        "content": [
            {
                "type": "text",
                "text": text,
            }
        ],
    }


def build_payload(messages: list[dict[str, str]], model: str, session_id: str, stream: bool = False) -> dict[str, Any]:
    return {
        "model": normalize_model(model),
        "max_tokens": 2048,
        "system": DEFAULT_SYSTEM_PROMPT,
        "messages": [to_claude_message(item["role"], item["content"]) for item in messages],
        "thinking": {"type": "adaptive"},
        "metadata": {
            "user_id": json.dumps(
                {
                    "device_id": "kg-rag-web-chat",
                    "account_uuid": "",
                    "session_id": session_id,
                },
                ensure_ascii=False,
                separators=(",", ":"),
            )
        },
        "output_config": {"effort": "medium"},
        "context_management": {
            "edits": [
                {
                    "type": "clear_thinking_20251015",
                    "keep": "all",
                }
            ]
        },
        "tools": [],
        "stream": stream,
    }


def extract_text(response_json: dict[str, Any]) -> str:
    chunks = []
    for item in response_json.get("content", []):
        if item.get("type") == "text":
            chunks.append(item.get("text", ""))
    return "".join(chunks).strip()


def _clean_preview(text: str, max_length: int = 240) -> str:
    cleaned = " ".join((text or "").split()).strip()
    return cleaned[:max_length]


def _extract_json_error(data: Any) -> str | None:
    if isinstance(data, dict):
        error = data.get("error")
        if isinstance(error, dict):
            for key in ("message", "detail", "error"):
                value = error.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()
        if isinstance(error, str) and error.strip():
            return error.strip()
        for key in ("detail", "message"):
            value = data.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return None


def _build_http_error(response: httpx.Response) -> UUAPIError:
    content_type = response.headers.get("content-type", "")
    preview = _clean_preview(response.text)
    message = None

    if "application/json" in content_type.lower():
        try:
            message = _extract_json_error(response.json())
        except ValueError:
            message = None

    if not message:
        lowered_preview = preview.lower()
        if response.status_code == 502 or "bad gateway" in lowered_preview:
            message = "上游 AI 服务暂时不可用（uuapi 返回 502 Bad Gateway），请稍后重试。"
        elif response.status_code == 503:
            message = "上游 AI 服务暂时不可用（503 Service Unavailable），请稍后重试。"
        elif response.status_code == 504:
            message = "上游 AI 服务响应超时（504 Gateway Timeout），请稍后重试。"
        else:
            message = f"上游 AI 服务请求失败（HTTP {response.status_code}）。"

    return UUAPIError(
        message,
        status_code=response.status_code,
        error_code="upstream_http_error",
        content_type=content_type,
        response_preview=preview,
    )


def _parse_json_response(response: httpx.Response) -> dict[str, Any]:
    content_type = response.headers.get("content-type", "")
    try:
        data = response.json()
    except ValueError as exc:
        preview = _clean_preview(response.text)
        raise UUAPIError(
            "上游 AI 服务返回了非 JSON 内容，当前无法解析，请稍后重试。",
            status_code=response.status_code,
            error_code="invalid_response_format",
            content_type=content_type,
            response_preview=preview,
        ) from exc

    if not isinstance(data, dict):
        raise UUAPIError(
            "上游 AI 服务返回的数据结构不是预期的 JSON 对象。",
            status_code=response.status_code,
            error_code="invalid_response_shape",
            content_type=content_type,
        )

    return data


def send_chat(
    messages: list[dict[str, str]],
    model: str,
    session_id: str | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
) -> dict[str, Any]:
    resolved_api_key = resolve_api_key(api_key)
    if not resolved_api_key:
        raise RuntimeError("Missing UUAPI API key. Set UUAPI_API_KEY or CLAUDE_PROXY_UPSTREAM_API_KEY.")

    resolved_session_id = session_id or str(uuid.uuid4())
    payload = build_payload(messages, model, resolved_session_id, stream=False)
    headers = build_headers(resolved_api_key, resolved_session_id)
    url = f"{(base_url or DEFAULT_BASE_URL).rstrip('/')}/v1/messages?beta=true"
    timeout = httpx.Timeout(connect=30.0, read=300.0, write=300.0, pool=30.0)

    with httpx.Client(timeout=timeout) as client:
        response = client.post(url, headers=headers, json=payload)
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise _build_http_error(exc.response) from exc

        data = _parse_json_response(response)
        return {
            "session_id": resolved_session_id,
            "model": data.get("model", normalize_model(model)),
            "text": extract_text(data),
            "raw": data,
        }
