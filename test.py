import os
from openai import OpenAI

for key in ["HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"]:
    os.environ.pop(key, None)

API_KEY = "sk-2ad2294a23410d8d46bb24213e3581109cd214a94a2fc7e617e2cb3e3abe2894"
BASE_URL = "https://uuapi.net/v1"
MODEL = "claude-opus-4-6"

client = OpenAI(
    api_key=API_KEY,
    base_url=BASE_URL,
)

response = client.chat.completions.create(
    model=MODEL,
    messages=[
        {"role": "system", "content": "你是一个测试助手。"},
        {"role": "user", "content": "请只返回 JSON 数组：[{\"head\":\"张三\",\"relation\":\"就职于\",\"tail\":\"OpenAI\",\"head_type\":\"人物\",\"tail_type\":\"组织\"}]"}
    ],
    temperature=0.1,
    max_tokens=200,
)

print(response.choices[0].message.content)
