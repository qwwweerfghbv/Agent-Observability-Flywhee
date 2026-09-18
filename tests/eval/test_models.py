"""快速测试不同模型"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.llm.client import QwenClient

api_key = "sk-sp-07b07d75bf8f477bbc62b1d25c6f9268"
models_to_test = ["qwen3-coder-plus"]

for model in models_to_test:
    try:
        client = QwenClient(api_key=api_key, model=model)
        result = client.chat_json_sync([{"role": "user", "content": "回复一个json格式的结果，包含ok字段"}], temperature=0.1)
        print(f"  ✅ {model}: {result}")
    except Exception as e:
        err_msg = str(e)[:100]
        print(f"  ❌ {model}: {err_msg}")
