import requests
import json

url = "https://free.easychat.top/api/organizations/92f90de5-36b1-48e5-9eaa-190b2361e9ee/chat_conversations/dfacdd84-499c-42c3-9931-83dd352f5f9b/completion"  # ⚠️注意：必须是真实 API，不是 /chat/uuid

headers = {
    "Accept": "text/event-stream",
    "Accept-Encoding": "gzip, deflate, br, zstd",
    "Accept-Language": "zh-CN,zh;q=0.8",
    "Connection": "keep-alive",
    "Content-Type": "application/json",
    "Origin": "https://free.easychat.top",
    "Referer": "https://free.easychat.top/chat/XXXX",
    "User-Agent": "Mozilla/5.0 ...",

    
    "Cookie": "Hm_lvt_edd8ee01c169597c375bafd592ac6531=1768321976; Hm_lpvt_edd8ee01c169597c375bafd592ac6531=1768321976; HMACCOUNT=6E60DFE517EFDDD3; easychat_session_key=jFfjdzIOrAIZVXqAOvJ3LOt1R1By4pHjLMNJ7PuIvH-dbnfnRM9vaTX6uu7kVTxTo7spASvLotX6nbupWhJJnMjn1-PglGHPKHlVrDtK5-m02QPXOQDWanD0sSiR_1E41-emTAzPtuh77DYL_UkPDqbXcSyI9HymSpVoR3ebRr4; activitySessionId=3cfde0f4-67d5-4faf-ba9b-1e2234009fba; anthropic-device-id=4be489db-c45b-4831-b797-ceda9f55ffa3; ajs_anonymous_id=claudeai.v1.9c199ff1-bcc9-4cbc-bebf-310900ba61d1; lastActiveOrg=92f90de5-36b1-48e5-9eaa-190b2361e9ee; CH-prefers-color-scheme=light; user-sidebar-visible-on-load=true; __ssid=c902aac5fcd205a3003f2e279a3e01a; __cf_bm=bPXtWTF4UxvGsgIHhhUzoajKZzG2BjhKyCSUSxOZSuc-1768323354-1.0.1.1-q1TYiuvfhmI_bz.YVjID5Y03JIQAOz_PNlnL.qXiC0Y3Ho_RkiA9JEIICEZrfuMC4rzNfJln3RNoe6qMMDujcBDbIMwMx.DHfEgAD10wvMg",
    "anthropic-device-id": "https://free.easychat.top/api/organizations/92f90de5-36b1-48e5-9eaa-190b2361e9ee/chat_conversations/dfacdd84-499c-42c3-9931-83dd352f5f9b/completion",
    "x-reclaude-nonce": "13beznro.ZGZhY2RkODQtNDk5Yy00MmMzLTk5MzEtODNkZDM1MmY1ZjliLjEzYmV6bnJvMTE5N2Q2NjYtMjYzYS00MmUwLTk5ZTMtMGE2MTRjNTgxNjlj",
}

payload = {
    "attachments": [],
    "files": [],
    "locale": "en-US",
    "model": "claude-sonnet-4-5-20250929",
    "prompt": "你是谁什么版本",
    "rendering_mode": "messages",
    "timezone": "Asia/Shanghai",
    "tools": [
        {"name": "web_search", "type": "web_search_v0"},
        {"name": "artifacts", "type": "artifacts_v0"},
        {"name": "repl", "type": "repl_v0"},
    ],
}

with requests.post(
    url,
    headers=headers,
    json=payload,
    stream=True,
    timeout=60
) as r:
    r.raise_for_status()

    for line in r.iter_lines(decode_unicode=True):
        if not line:
            continue
        if line.startswith("data:"):
            data = line[5:].strip()
            if data == "[DONE]":
                print("\n[DONE]")
                break
            try:
                obj = json.loads(data)
                print(obj, flush=True)
            except json.JSONDecodeError:
                print(data, flush=True)
