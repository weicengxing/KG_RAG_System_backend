# Claude Code Transparent Proxy

这个脚本的用途是：

- 接收 Claude Code 发来的原始请求
- 把请求头和请求体落盘，便于分析真实格式
- 尽量透明地转发到 `https://uuapi.net`

## 运行方式

在 `D:\KG_RAG_System\backend` 下执行：

```powershell
$env:CLAUDE_PROXY_UPSTREAM_BASE_URL="https://uuapi.net"
$env:CLAUDE_PROXY_UPSTREAM_API_KEY="你的key"
$env:CLAUDE_PROXY_UPSTREAM_AUTH_MODE="bearer"
.\venv\Scripts\python.exe -m uvicorn claude_proxy:app --host 0.0.0.0 --port 8088
```

## Claude Code 侧配置

把 Claude Code 指到这个代理：

```powershell
$env:ANTHROPIC_BASE_URL="http://127.0.0.1:8088"
$env:ANTHROPIC_AUTH_TOKEN="任意占位值"
```

如果 Claude Code 要求的是 `ANTHROPIC_API_KEY`，也可以改成：

```powershell
$env:ANTHROPIC_BASE_URL="http://127.0.0.1:8088"
$env:ANTHROPIC_API_KEY="任意占位值"
```

代理会把上游 key 强制替换成 `CLAUDE_PROXY_UPSTREAM_API_KEY`。

`CLAUDE_PROXY_UPSTREAM_AUTH_MODE` 支持：

- `bearer`：转发为 `Authorization: Bearer <key>`
- `x-api-key`：转发为 `x-api-key: <key>`
- `both`：两种都带上
- `passthrough`：保留 Claude Code 原始认证头，不替换

## 抓包结果

日志目录默认在：

```text
D:\KG_RAG_System\backend\logs\claude_proxy
```

关键文件：

- `requests.jsonl`：每次请求的元信息
- `responses.jsonl`：每次响应的状态和头
- `request_bodies\*.bin`：原始请求体
- `response_bodies\*.bin`：原始响应体

## 说明

- 这个代理优先用于分析真实请求，不是生产级网关。
- 它会尽量保留 Claude Code 的原始头部，只移除少数 hop-by-hop 头。
- 如果 `uuapi.net` 依赖某些 Claude Code 私有特征，这个方案最容易把它们保留下来。
