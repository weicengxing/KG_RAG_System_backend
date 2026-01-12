from openai import OpenAI

client = OpenAI(
   base_url="https://integrate.api.nvidia.com/v1",
   api_key="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"
)

messages = []

def chat(user_input):
   messages.append({"role": "user", "content": user_input})
   
   try:
       completion = client.chat.completions.create(
           model="minimaxai/minimax-m2.1",
           messages=messages,
           temperature=1,
           top_p=0.95,
           max_tokens=8192,
           stream=True
       )
       
       assistant_reply = ""
       print("助手: ", end="", flush=True)
       
       for chunk in completion:
           if (chunk.choices and 
               chunk.choices[0].delta.content):
               content = chunk.choices[0].delta.content
               print(content, end="", flush=True)
               assistant_reply += content
       
       print()
       messages.append({"role": "assistant", "content": assistant_reply})
       
   except Exception as e:
       print(f"\n错误: {e}")
       messages.pop()

print("=" * 50)
print("连续对话模式 (输入 'exit' 退出)")
print("=" * 50)

while True:
   try:
       user_input = input("\n你: ").strip()
       if user_input.lower() in ['exit', 'quit', '退出']:
           break
       if user_input:
           chat(user_input)
   except (KeyboardInterrupt, EOFError):
       break

print("\n再见！")
