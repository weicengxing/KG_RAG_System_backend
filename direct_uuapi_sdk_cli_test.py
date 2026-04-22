import argparse
import json
import os
import sys
import time
import uuid
from pathlib import Path

import httpx


DEFAULT_BASE_URL = "https://uuapi.net"
DEFAULT_TEMPLATE_BODY = Path(__file__).resolve().parent / "logs" / "claude_proxy_compare" / "request_bodies" / "633cbc19-e18e-46e2-b983-9c3a10022e10.bin"
DEFAULT_MODEL = "claude-opus-4-7"
DEFAULT_DEVICE_ID = "840fca4ea1d9819aa21398e57e346ee6b69a21b823537bf13f2a689b09abac4a"
DEFAULT_BETA = ",".join(
    [
        "claude-code-20250219",
        "context-1m-2025-08-07",
        "interleaved-thinking-2025-05-14",
        "context-management-2025-06-27",
        "prompt-caching-scope-2026-01-05",
        "effort-2025-11-24",
    ]
)


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


def load_template(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def replace_session_metadata(payload: dict, session_id: str, device_id: str) -> None:
    payload["metadata"] = {
        "user_id": json.dumps(
            {
                "device_id": device_id,
                "account_uuid": "",
                "session_id": session_id,
            },
            separators=(",", ":"),
        )
    }


def replace_prompt(payload: dict, prompt: str) -> None:
    messages = payload.get("messages", [])
    if not messages:
        payload["messages"] = [{"role": "user", "content": [{"type": "text", "text": prompt}]}]
        return

    content = messages[0].get("content", [])
    if not content:
        messages[0]["content"] = [{"type": "text", "text": prompt}]
        return

    for item in reversed(content):
        if item.get("type") == "text":
            item["text"] = prompt
            return

    content.append({"type": "text", "text": prompt})


def maybe_trim_template(payload: dict, trim_tools: bool, trim_reminders: bool) -> None:
    if trim_tools:
        payload["tools"] = []

    if trim_reminders:
        messages = payload.get("messages", [])
        if messages and isinstance(messages[0].get("content"), list):
            content = messages[0]["content"]
            keep = []
            for idx, item in enumerate(content):
                if idx == len(content) - 1:
                    keep.append(item)
                    continue
                text = item.get("text", "")
                if "<system-reminder>" not in text:
                    keep.append(item)
            messages[0]["content"] = keep


def build_headers(api_key: str, session_id: str) -> dict[str, str]:
    return {
        "accept": "application/json",
        "x-stainless-retry-count": "0",
        "x-stainless-timeout": "300",
        "x-stainless-lang": "js",
        "x-stainless-package-version": "0.81.0",
        "x-stainless-os": "Windows",
        "x-stainless-arch": "x64",
        "x-stainless-runtime": "node",
        "x-stainless-runtime-version": "v25.9.0",
        "anthropic-dangerous-direct-browser-access": "true",
        "anthropic-version": "2023-06-01",
        "x-app": "cli",
        "user-agent": "claude-cli/2.1.112 (external, sdk-cli)",
        "x-claude-code-session-id": session_id,
        "authorization": f"Bearer {api_key}",
        "content-type": "application/json",
        "anthropic-beta": DEFAULT_BETA,
        "accept-language": "*",
        "sec-fetch-mode": "cors",
        "accept-encoding": "gzip, deflate",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Replay a closer-to-real Claude Code SDK CLI request against uuapi.")
    parser.add_argument("--prompt", default="请只回复：测试成功", help="Prompt text to inject into the template.")
    parser.add_argument("--api-key", default=os.getenv("UUAPI_API_KEY", ""), help="Gateway API key.")
    parser.add_argument("--base-url", default=os.getenv("UUAPI_BASE_URL", DEFAULT_BASE_URL), help="Gateway base URL.")
    parser.add_argument("--template-body", default=str(DEFAULT_TEMPLATE_BODY), help="Captured Claude Code request body template.")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Override model name.")
    parser.add_argument("--max-tokens", type=int, default=0, help="Override max_tokens when > 0.")
    parser.add_argument("--effort", default="", help="Override output_config.effort.")
    parser.add_argument("--device-id", default=DEFAULT_DEVICE_ID, help="Device ID to put in metadata.user_id.")
    parser.add_argument("--trim-tools", action="store_true", help="Clear the tools list before sending.")
    parser.add_argument("--trim-reminders", action="store_true", help="Remove leading <system-reminder> content blocks.")
    parser.add_argument("--dump-payload", action="store_true", help="Print the final JSON payload before sending.")
    args = parser.parse_args()

    if not args.api_key:
        print("Missing API key. Pass --api-key or set UUAPI_API_KEY.", file=sys.stderr)
        return 2

    template_path = Path(args.template_body)
    if not template_path.exists():
        print(f"Template body not found: {template_path}", file=sys.stderr)
        return 2

    session_id = str(uuid.uuid4())
    payload = load_template(template_path)
    payload["model"] = args.model or payload.get("model", DEFAULT_MODEL)
    if args.max_tokens > 0:
        payload["max_tokens"] = args.max_tokens
    if args.effort:
        payload.setdefault("output_config", {})
        payload["output_config"]["effort"] = args.effort
    replace_session_metadata(payload, session_id, args.device_id)
    replace_prompt(payload, args.prompt)
    maybe_trim_template(payload, trim_tools=args.trim_tools, trim_reminders=args.trim_reminders)
    headers = build_headers(args.api_key, session_id)

    if args.dump_payload:
        safe_write(json.dumps(payload, ensure_ascii=False, indent=2))

    url = f"{args.base_url.rstrip('/')}/v1/messages?beta=true"
    timeout = httpx.Timeout(connect=30.0, read=300.0, write=300.0, pool=30.0)
    with httpx.Client(timeout=timeout) as client:
        started = time.perf_counter()
        response = client.post(url, headers=headers, json=payload)
        elapsed = time.perf_counter() - started
        safe_write(f"HTTP {response.status_code}")
        safe_write(f"ELAPSED_SECONDS={elapsed}")
        safe_write(f"Content-Type: {response.headers.get('content-type', '')}")
        safe_write(response.text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
