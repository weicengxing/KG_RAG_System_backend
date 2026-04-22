# Direct uuapi Test

这个脚本用于脱离 Claude Code，直接向 `uuapi.net` 发送 Claude Code 风格的最小请求。

## 运行

```powershell
cd D:\KG_RAG_System\backend
$env:UUAPI_API_KEY="你的key"
.\venv\Scripts\python.exe .\direct_uuapi_test.py --prompt "你好"
```

流式模式：

```powershell
.\venv\Scripts\python.exe .\direct_uuapi_test.py --prompt "你好" --stream
```

如果你想先看发送出去的 JSON：

```powershell
.\venv\Scripts\python.exe .\direct_uuapi_test.py --prompt "你好" --dump-payload
```

## 说明

- 这个脚本会模拟 Claude Code 的关键 headers 和 body 结构。
- 它不是完整复刻 Claude Code，只是当前抓包基础上的最小可用版本。
- 如果后续要提高成功率，可以继续从代理日志里补充更多 `system` 或 `metadata` 字段。
