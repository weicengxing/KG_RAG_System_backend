import requests
import json

# 接口地址/密钥/模型 统一配置（这里不用改，你的信息都保留了）
url = "https://api.lhyb.dpdns.org/v1/chat/completions"
api_key = "sk-WGOCGHbfZAjX0G2nT0rYckllyOcby1RBcwTnNwJhONUEiJfE"
model = "gemini-3-flash-preview-thinking"

# 请求头固定配置
headers = {
    'Accept': 'application/json',
    'Authorization': f'Bearer {api_key}',
    'Content-Type': 'application/json'
}

print("✅ 模型对话已启动，输入内容按回车发送，输入 exit 即可退出程序")
print("-" * 60)

# 无限循环：持续接收输入 + 发送请求
while True:
    # 1. 获取终端输入的内容
    user_input = input("你: ")
    
    # 退出指令：输入 exit 或 退出 就终止程序
    if user_input.strip().lower() in ["exit", "退出"]:
        print("👋 对话结束，程序已退出")
        break
    
    # 过滤空输入（防止只按回车发送空内容）
    if not user_input.strip():
        print("⚠️  请输入有效内容后再发送！")
        continue

    # 2. 构造请求体（根据输入动态生成，不再硬编码）
    payload = json.dumps({
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": user_input
            }
        ]
    })

    try:
        # 3. 发送POST请求到接口
        response = requests.post(url, headers=headers, data=payload, timeout=30)
        # 4. 解析响应结果
        response_data = response.json()
        # 5. 提取AI回复的内容并打印
        ai_content = response_data["choices"][0]["message"]["content"]
        print(f"AI: {ai_content}")
        
    except Exception as e:
        # 异常捕获：网络问题/接口报错/解析失败 都能提示具体原因
        print(f"❌ 请求失败，错误信息：{str(e)}")
        
    print("-" * 60)