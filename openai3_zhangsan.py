import requests
import json
import sys

# 强制控制台使用 UTF-8
sys.stdout.reconfigure(encoding='utf-8')
sys.stdin.reconfigure(encoding='utf-8')

API_KEY = "sk-r0QnvIfixN70kxblq2AuQcfFslZNDlb1xy31I20GWQmBqnTy"
BASE_URL = "https://terminal.pub/v1/messages"
MODEL = "claude-opus-4-6"

headers = {
    "Content-Type": "application/json; charset=utf-8",
    "X-API-Key": API_KEY
}

conversation = []

print("开始聊天（输入 exit 退出）\n")

while True:
    user_input = input("你: ")

    if user_input.lower() in ["exit", "quit"]:
        break

    conversation.append({
        "role": "user",
        "content": user_input
    })

    payload = {
        "model": MODEL,
        "max_tokens": 1024,
        "messages": conversation
    }

    try:
        response = requests.post(
            BASE_URL,
            headers=headers,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8")
        )

        data = response.json()

        if "error" in data:
            print("错误:", data)
            continue

        reply = data["content"][0]["text"]

        print("Claude:", reply, "\n")

        conversation.append({
            "role": "assistant",
            "content": reply
        })

    except Exception as e:
        print("请求失败:", e)