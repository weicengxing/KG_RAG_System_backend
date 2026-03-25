import os
import sys
import requests

API_URL = "https://api.fireworks.ai/inference/v1/chat/completions"
MODEL = "accounts/fireworks/models/glm-5"

# ✅ 建议把 token 放到环境变量，避免写进代码
# Windows (PowerShell): setx CANOPYWAVE_TOKEN "你的token"
# macOS/Linux: export CANOPYWAVE_TOKEN="你的token"
TOKEN = os.getenv("CANOPYWAVE_TOKEN") or "fw_Vnd2JhcaY7q6TnY91VUYH6"

HEADERS = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {TOKEN}",
}

def chat(messages, max_tokens=1000, temperature=1, timeout=60):
    payload = {
        "model": MODEL,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    r = requests.post(API_URL, headers=HEADERS, json=payload, timeout=timeout)
    r.raise_for_status()
    data = r.json()

    # 兼容常见 OpenAI 风格返回：choices[0].message.content
    try:
        return data["choices"][0]["message"]["content"]
    except Exception:
        # 如果返回结构不同，打印出来方便你调整解析
        raise RuntimeError(f"Unexpected response format: {data}")

def main():
    if not TOKEN or "把你的token放这里" in TOKEN:
        print("请先设置 CANOPYWAVE_TOKEN 环境变量，或在代码里填入 token。")
        sys.exit(1)

    # 你可以加 system 角色，定义助手风格/规则
    messages = [
        {"role": "system", "content": "你是一个有帮助的中文助手。"}
    ]

    print("✅ 连续对话已启动。输入 /exit 退出，/reset 清空上下文。\n")

    while True:
        user_text = input("你：").strip()
        if not user_text:
            continue
        if user_text.lower() in ["/exit", "exit", "quit", "q"]:
            print("已退出。")
            break
        if user_text.lower() == "/reset":
            messages = [{"role": "system", "content": "你是一个有帮助的中文助手。"}]
            print("✅ 已清空上下文。\n")
            continue

        # 追加用户消息
        messages.append({"role": "user", "content": user_text})

        try:
            assistant_text = chat(messages)
        except requests.HTTPError as e:
            print(f"\n❌ HTTP 错误：{e}\n响应内容：{getattr(e.response, 'text', '')}\n")
            # 出错时把最后一条 user 消息弹出，避免坏状态污染上下文
            messages.pop()
            continue
        except Exception as e:
            print(f"\n❌ 错误：{e}\n")
            messages.pop()
            continue

        # 追加助手消息（关键：这样才能连续对话）
        messages.append({"role": "assistant", "content": assistant_text})
        print(f"\n助手：{assistant_text}\n")

if __name__ == "__main__":
    main()
