"""测试JD解析的LLM返回"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.llm.client import QwenClient, set_llm_client
from app.llm.prompts import PromptTemplates

api_key = "sk-sp-07b07d75bf8f477bbc62b1d25c6f9268"
client = QwenClient(api_key=api_key, model="qwen3-coder-plus")
set_llm_client(client)

# 测试JP-001的JD文本
jd_text = """AI测试开发工程师
杭州 · 某AI独角兽科技有限公司
30-45K × 15薪

职位描述：
1. 负责公司AI产品的自动化测试框架设计与开发
2. 设计Agent评测方案，包括任务完成率、幻觉检测、安全性评估等指标
3. 搭建CI/CD测试流水线，提升测试效率

任职要求：
1. 本科及以上学历，计算机相关专业
2. 3年以上测试开发经验
3. 精通Python，熟悉pytest/Selenium等测试框架
4. 有AI模型测试或Agent评测经验者优先

公司信息：
B轮融资，团队规模500人，人工智能行业"""

prompt = PromptTemplates.format_template("PARSE_JD", jd_text=jd_text)
messages = [{"role": "user", "content": prompt}]

print("=== 调用LLM ===")
try:
    result = client.chat_json_sync(messages, temperature=0.3)
    print(f"返回类型: {type(result)}")
    print(f"返回内容: {result}")
except Exception as e:
    print(f"调用失败: {e}")
