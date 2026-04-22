"""
Claude Code gateway entrypoint.

This file reuses the existing transparent proxy app so Claude Code can
send requests to our local gateway, while keeping a clearer filename for
running and sharing with others.
"""

import os

import uvicorn

from claude_proxy import app


def main() -> None:
    host = os.getenv("CLAUDE_GATEWAY_HOST", "127.0.0.1")
    port = int(os.getenv("CLAUDE_GATEWAY_PORT", "8088"))
    uvicorn.run("claude_code_gateway:app", host=host, port=port, reload=False)


if __name__ == "__main__":
    main()
