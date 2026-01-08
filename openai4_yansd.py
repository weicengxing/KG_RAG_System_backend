from openai import OpenAI

client = OpenAI(
  base_url = "https://integrate.api.nvidia.com/v1",
  api_key = "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"
)

completion = client.chat.completions.create(
  model="z-ai/glm4.7",
  messages=[{"role":"user","content":"你是谁什么版本。"}],
  temperature=1,
  top_p=0.95,
  max_tokens=8192,
  stream=True
)

for chunk in completion:
  if chunk.choices[0].delta.content is not None:
    print(chunk.choices[0].delta.content, end="")
  

