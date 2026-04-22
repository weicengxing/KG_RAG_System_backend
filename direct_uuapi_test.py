import argparse
import json
import os
import sys
import uuid
from typing import Any

import httpx


DEFAULT_BASE_URL = "https://uuapi.net"
DEFAULT_MODEL = "claude-opus-4-6"
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


def build_payload(prompt: str, model: str, stream: bool, session_id: str) -> dict[str, Any]:
    return {
        "model": model,
        "max_tokens": 1024,
        "system": DEFAULT_SYSTEM_PROMPT,
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": prompt,
                    }
                ],
            }
        ],
        "thinking": {"type": "adaptive"},
        "metadata": {
            "user_id": json.dumps(
                {
                    "device_id": "direct-uuapi-test",
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


def print_stream_response(response: httpx.Response) -> None:
    for line in response.iter_lines():
        if not line:
            continue
        safe_write(line)


def print_json_response(response: httpx.Response) -> None:
    try:
        payload = response.json()
        safe_write(json.dumps(payload, ensure_ascii=False, indent=2))
    except json.JSONDecodeError:
        safe_write(response.text)


def safe_write(text: str) -> None:
    try:
        print(text)
    except UnicodeEncodeError:
        buffer = getattr(sys.stdout, "buffer", None)
        if buffer is not None:
            buffer.write(text.encode("utf-8", errors="replace"))
            buffer.write(b"\n")
        else:
            print(text.encode("ascii", errors="backslashreplace").decode("ascii"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Send a Claude Code-style request directly to uuapi.")
    parser.add_argument("--prompt", default="你好", help="User prompt text.")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Model id to send.")
    parser.add_argument("--base-url", default=os.getenv("UUAPI_BASE_URL", DEFAULT_BASE_URL), help="Gateway base URL.")
    parser.add_argument("--api-key", default=os.getenv("UUAPI_API_KEY", ""), help="Gateway API key.")
    parser.add_argument("--stream", action="store_true", help="Request SSE streaming output.")
    parser.add_argument("--dump-payload", action="store_true", help="Print the JSON payload before sending.")
    args = parser.parse_args()

    if not args.api_key:
        print("Missing API key. Pass --api-key or set UUAPI_API_KEY.", file=sys.stderr)
        return 2

    session_id = str(uuid.uuid4())
    payload = build_payload(args.prompt, args.model, args.stream, session_id)
    headers = build_headers(args.api_key, session_id)
    url = f"{args.base_url.rstrip('/')}/v1/messages?beta=true"

    if args.dump_payload:
        print(json.dumps(payload, ensure_ascii=False, indent=2))

    timeout = httpx.Timeout(connect=30.0, read=300.0, write=300.0, pool=30.0)
    with httpx.Client(timeout=timeout) as client:
        response = client.post(url, headers=headers, json=payload)
        print(f"HTTP {response.status_code}")
        print(f"Content-Type: {response.headers.get('content-type', '')}")

        if "text/event-stream" in response.headers.get("content-type", "").lower():
            print_stream_response(response)
        else:
            print_json_response(response)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
