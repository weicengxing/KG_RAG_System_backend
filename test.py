import os
from openai import OpenAI

for key in ["HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"]:
    os.environ.pop(key, None)

API_KEY = "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"
BASE_URL = "https://openrouter.ai/api/v1"
MODEL = "qwen/qwen3.6-plus:free"

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
