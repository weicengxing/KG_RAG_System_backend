import requests
import json

URL = "https://yansd666.com/pg/chat/completions"

# 把这里改成你自己的 session 和 new-api-user
SESSION_COOKIE = "session=MTc2NzA2MzE4OHxEWDhFQVFMX2dBQUJFQUVRQUFEXzFmLUFBQVlHYzNSeWFXNW5EQW9BQ0hWelpYSnVZVzFsQm5OMGNtbHVad3dJQUFaM1pXa3dNRElHYzNSeWFXNW5EQVlBQkhKdmJHVURhVzUwQkFJQUFnWnpkSEpwYm1jTUNBQUdjM1JoZEhWekEybHVkQVFDQUFJR2MzUnlhVzVuREFjQUJXZHliM1Z3Qm5OMGNtbHVad3dKQUFka1pXWmhkV3gwQm5OMGNtbHVad3dQQUExelpYTnphVzl1WDNSdmEyVnVCbk4wY21sdVp3d2lBQ0JtT0dWalptSmhabUl3TVRFME16aGlZVFk0TVRjeVkyUmtNR1ZqTXpKa05nWnpkSEpwYm1jTUJBQUNhV1FEYVc1MEJBVUFfUVZlcGc9PXwwMkE84epvJybY4a0NOtq-Rkiba1LDFF0TlOuGQxHVEw=="
NEW_API_USER = "175955"  # 比如 175955

headers = {
   "Content-Type": "application/json",
   "Accept": "text/event-stream",
   "Cookie": SESSION_COOKIE,
   "new-api-user": NEW_API_USER,
   # User-Agent 可以用简单一点的
   "User-Agent": "python-requests/2.x",
}

payload = {
   "model": "claude-opus-4-5-20251101",
   "group": "default",
   "messages": [
       {"role": "user", "content": "你是谁什么版本？"},
       # 如果你想把历史对话也带上，就继续追加 role/ content
   ],
   "stream": True,
   "temperature": 1,
   "top_p": 1,
   "presence_penalty": 0,
   "frequency_penalty": 0,
}

def call_api():
   # stream=True 让 requests 按行流式读取响应
   with requests.post(URL, headers=headers, json=payload, stream=True, timeout=300) as resp:
       resp.raise_for_status()
       resp.encoding = 'utf-8'
       full_text = []

       for line in resp.iter_lines(decode_unicode=True):
           if not line:
               continue

           # SSE 每个事件行通常形如：data: {...}
           if line.startswith("data: "):
               data_str = line[len("data: "):].strip()

               if data_str == "[DONE]":
                   break

               try:
                   chunk = json.loads(data_str)
               except json.JSONDecodeError:
                   print("\n[解析失败] 原始行:", data_str)
                   continue

               # 按你贴的数据结构来取内容
               try:
                   delta = chunk["choices"][0]["delta"]
                   content = delta.get("content")
                   if content:
                       print(content, end="", flush=True)
                       full_text.append(content)
               except (KeyError, IndexError) as e:
                   print("\n[结构不符] chunk:", chunk, "错误:", e)

       



if __name__ == "__main__":
   call_api()
