from openai import OpenAI

client = OpenAI(
    base_url='https://api-inference.modelscope.cn/v1',
    api_key='ms-7ae9b437-2d5d-47c9-b613-86e012766c2c', # ModelScope Token
)

response = client.chat.completions.create(
    model='ZhipuAI/GLM-4.7', # ModelScope Model-Id, required
    messages=[
        {
            'role': 'user',
            'content': '你好你是谁什么版本'
        }
    ],
    stream=True
)
done_reasoning = False
for chunk in response:
    if chunk.choices:
        reasoning_chunk = chunk.choices[0].delta.reasoning_content
        answer_chunk = chunk.choices[0].delta.content
        if reasoning_chunk != '':
            print(reasoning_chunk, end='', flush=True)
        elif answer_chunk != '':
            if not done_reasoning:
                print('\n\n === Final Answer ===\n')
                done_reasoning = True
            print(answer_chunk, end='', flush=True)