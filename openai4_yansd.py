import requests
import json

url = "https://inference.canopywave.io/v1/chat/completions"
headers = {
   "Content-Type": "application/json",
   "Authorization": "Bearer vqIXTEbH5sKWHOy2hvntAwjKM5C_4gbgX_5UZgZbgrM"  # ⚠️ 真实调用请换成新的 key
}
data = {
   "model": "deepseek-chat-v3.2-speciale",
   "messages": [
       {"role": "user", "content": "你好，请介绍一下自己"}
   ],
   "max_tokens": 500,
   "temperature": 0.7
}

response = requests.post(url, headers=headers, json=data)
print(response.status_code)
print(response.text)          # 先看原始返回
result = response.json()
print(result.keys())          # 看顶层有哪些键
