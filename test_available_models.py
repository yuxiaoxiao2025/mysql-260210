"""
测试当前 API Key 可用的通义千问模型列表
"""
import os
import dashscope
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 配置 API Key
api_key = os.getenv("DASHSCOPE_API_KEY")
if not api_key:
    print("Error: DASHSCOPE_API_KEY not found")
    exit(1)

dashscope.api_key = api_key

print("=" * 60)
print("Testing available Qwen models with current API Key")
print("=" * 60)
print(f"API Key: sk-{api_key[3:20]}...")
print()

# 通义千问主要模型列表 (包括 Qwen3.5)
models_to_test = [
    # Qwen3.5 系列 (最新)
    "qwen3.5",
    "qwen3.5-72b-instruct",
    "qwen3.5-32b-instruct",
    
    # Qwen3 系列
    "qwen3-235b-a22b",
    "qwen3-30b-a3b",
    
    # Qwen2.5 系列
    "qwen2.5-72b-instruct",
    "qwen2.5-32b-instruct", 
    "qwen2.5-14b-instruct",
    "qwen2.5-7b-instruct",
    
    # 商业版模型
    "qwen-max",
    "qwen-plus",
    "qwen-turbo",
    
    # 长文本模型
    "qwen-long",
    
    # 代码模型
    "qwen-coder-plus",
    "qwen-coder-turbo",
]

print("Testing models...\n")
print(f"{'Model Name':<30} {'Status':<10} {'Notes'}")
print("-" * 60)

available_models = []

for model in models_to_test:
    try:
        response = dashscope.Generation.call(
            model=model,
            messages=[
                {'role': 'system', 'content': 'You are a helpful assistant.'},
                {'role': 'user', 'content': 'Hi'}
            ],
            max_tokens=5
        )
        
        if response.status_code == 200:
            print(f"OK   {model:<30} {'Available':<10}")
            available_models.append(model)
        else:
            print(f"FAIL {model:<30} {'Error':<10} {response.code}: {response.message}")
            
    except Exception as e:
        print(f"FAIL {model:<30} {'Exception':<10} {str(e)}")

print()
print("=" * 60)
print(f"Summary: {len(available_models)} models available")
if available_models:
    print("Available models:")
    for m in available_models:
        print(f"  - {m}")
print("=" * 60)
