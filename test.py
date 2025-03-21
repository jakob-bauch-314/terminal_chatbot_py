from langchain_ollama import OllamaLLM
import datetime

print("start:", datetime.datetime.now())
model = OllamaLLM(model="deepseek-r1")
print("loaded model:", datetime.datetime.now())

for i in range(1, 10):
    result = model.invoke("hello world!")
    print(f"{i}. response:", datetime.datetime.now(), f"({result})")