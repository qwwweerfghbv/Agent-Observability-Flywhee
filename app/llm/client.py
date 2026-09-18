"""LLM客户端封装 - 统一接口

提供同步和异步两种调用方式：
- chat_json() / chat(): 异步方法，适用于 async 上下文
- chat_json_sync() / chat_sync(): 同步方法，适用于普通函数调用

MockClient 为同步方法，返回有意义的 mock 数据用于测试。
"""
import json
import asyncio
import threading
import time
from typing import Optional, Dict, Any, List
from loguru import logger

from app.core.config import settings
from app.observability.context import add_llm_metrics, fill, get_context


# ===== Token消耗统计（供评测报告使用）=====
_token_stats = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "calls": 0}


def get_token_stats() -> Dict[str, int]:
    """获取累计Token消耗（自上次reset以来）"""
    return dict(_token_stats)


def reset_token_stats() -> None:
    """清零Token统计"""
    for key in _token_stats:
        _token_stats[key] = 0


def _accumulate_usage(usage) -> None:
    """累加一次LLM调用的usage统计"""
    if usage is None:
        return
    _token_stats["prompt_tokens"] += getattr(usage, "prompt_tokens", 0) or 0
    _token_stats["completion_tokens"] += getattr(usage, "completion_tokens", 0) or 0
    _token_stats["total_tokens"] += getattr(usage, "total_tokens", 0) or 0
    _token_stats["calls"] += 1


def _usage_dict(usage) -> Optional[Dict[str, int]]:
    """usage → 观测用 tokens dict（SDD §4.3）"""
    if usage is None:
        return None
    return {"prompt": getattr(usage, "prompt_tokens", 0) or 0,
            "completion": getattr(usage, "completion_tokens", 0) or 0,
            "total": getattr(usage, "total_tokens", 0) or 0}


def _classify_llm_error(e: Exception) -> str:
    """LLM 异常分类（401/429/5xx/timeout，US-O5 / B12）"""
    status = getattr(e, "status_code", None)
    if status == 401:
        return "auth_401"
    if status == 429:
        return "rate_limit_429"
    if status and 500 <= int(status) < 600:
        return f"server_{status}"
    name = type(e).__name__
    if "Timeout" in name or "timeout" in str(e).lower():
        return "timeout"
    return f"{name}: {str(e)[:120]}"


class LLMClient:
    """LLM客户端基类"""
    
    def __init__(self, api_key: str, model: str, base_url: Optional[str] = None):
        self.api_key = api_key
        self.model = model
        self.base_url = base_url
        self._client = None
    
    def _get_client(self):
        """延迟初始化客户端（带超时配置，防止请求无限挂起）"""
        if self._client is None:
            from openai import OpenAI
            kwargs = {"api_key": self.api_key, "timeout": settings.llm_timeout}
            if self.base_url:
                kwargs["base_url"] = self.base_url
            self._client = OpenAI(**kwargs)
        return self._client
    
    # ===== 异步方法 =====
    
    async def chat(self, messages: List[Dict[str, str]], temperature: float = 0.7, 
             max_tokens: int = 2000, response_format: Optional[Dict] = None,
             timeout: Optional[float] = None) -> str:
        """发送聊天请求（异步，SDK调用放入线程池避免阻塞事件循环）

        L2 观测埋点（SDD §4.3）：耗时/tokens/model 就地填充，异常分类记录；静默降级。
        timeout：单次请求超时（秒），覆盖客户端默认值；大输出结构化调用需放宽。
        """
        t0 = time.time()
        try:
            def _call():
                client = self._get_client()
                kwargs = {
                    "model": self.model,
                    "messages": messages,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                }
                if response_format:
                    kwargs["response_format"] = response_format
                if timeout:
                    kwargs["timeout"] = timeout
                return client.chat.completions.create(**kwargs)

            response = await asyncio.get_event_loop().run_in_executor(None, _call)
            _accumulate_usage(getattr(response, "usage", None))
            if get_context():
                fill(model=getattr(response, "model", None) or self.model)
                add_llm_metrics(tokens=_usage_dict(getattr(response, "usage", None)),
                                duration_ms=round((time.time() - t0) * 1000, 1))
            return response.choices[0].message.content
        except Exception as e:
            fill(llm_error=_classify_llm_error(e))
            logger.error(f"LLM调用失败: {e}")
            raise

    def chat_stream(self, messages: List[Dict[str, str]], temperature: float = 0.7,
                    max_tokens: int = 2000, usage_holder: Optional[Dict[str, int]] = None):
        """流式聊天，逐段 yield 文本增量（同步生成器）。

        注：流式 chunk 读取为阻塞网络IO，适用于单用户本地场景；
        失败时抛出异常，由调用方降级处理。

        usage_holder：可选可变 dict。开启 include_usage 后，末尾 chunk 带回 usage
        （choices 为空），就地写入供上层回填 tokens（SDD §4.3）。
        """
        client = self._get_client()
        try:
            response = client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=True,
                stream_options={"include_usage": True},
            )
            for chunk in response:
                # include_usage: 末尾 chunk choices 为空但携 usage，先采集再跳过
                u = getattr(chunk, "usage", None)
                if u is not None:
                    _accumulate_usage(u)
                    if usage_holder is not None:
                        usage_holder.update(_usage_dict(u) or {})
                if not chunk.choices:
                    continue
                delta = getattr(chunk.choices[0].delta, "content", None)
                if delta:
                    yield delta
        except Exception as e:
            fill(llm_error=_classify_llm_error(e))  # 可能在线程内（无上下文时静默 no-op）
            logger.error(f"LLM流式调用失败: {e}")
            raise

    async def chat_stream_async(self, messages: List[Dict[str, str]], temperature: float = 0.7,
                                max_tokens: int = 2000):
        """异步流式聊天：线程+Queue 桥接同步生成器。

        直接在 async 上下文用 for 迭代同步生成器会阻塞事件循环，
        导致 SSE 帧积压、流式退化为整段突发；桥接后每个 delta
        之间都有 await 点，事件循环可及时 flush 帧。
        """
        queue: asyncio.Queue = asyncio.Queue()
        loop = asyncio.get_event_loop()
        usage_holder: Dict[str, int] = {}

        def _producer():
            try:
                for delta in self.chat_stream(messages, temperature, max_tokens, usage_holder):
                    loop.call_soon_threadsafe(queue.put_nowait, ("delta", delta))
                # 流正常结束：先回填 usage（tokens）再发 end
                loop.call_soon_threadsafe(queue.put_nowait, ("usage", dict(usage_holder)))
                loop.call_soon_threadsafe(queue.put_nowait, ("end", None))
            except Exception as e:  # noqa: BLE001
                loop.call_soon_threadsafe(queue.put_nowait, ("error", e))

        threading.Thread(target=_producer, daemon=True).start()
        t0 = time.time()
        first = True
        while True:
            kind, payload = await queue.get()
            if kind == "end":
                return
            if kind == "usage":
                if payload:  # 只补 tokens，不重复计 llm_calls（首 delta 已计）
                    add_llm_metrics(tokens=payload, count_call=False)
                continue
            if kind == "error":
                fill(llm_error=_classify_llm_error(payload))
                raise payload
            if first:
                fill(llm_first_delta_ms=round((time.time() - t0) * 1000, 1),
                     model=self.model)
                add_llm_metrics()  # 计一次流式调用（tokens 末尾 usage chunk 回填）
                first = False
            yield payload
    
    async def chat_json(self, messages: List[Dict[str, str]], temperature: float = 0.3,
                        max_tokens: int = 2000, timeout: Optional[float] = None) -> Dict[str, Any]:
        """发送聊天请求并解析JSON响应（异步）

        max_tokens：结构化输出（简历/JD 解析等）体积大，默认 2000 易截断产生
        残缺 JSON，调用方可按需放大；timeout 同步放宽防长生成超时。
        """
        try:
            response = await self.chat(
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                response_format={"type": "json_object"},
                timeout=timeout
            )
            return json.loads(response)
        except json.JSONDecodeError as e:
            logger.error(f"JSON解析失败: {e}, 响应: {response[:500]}")
            return self._extract_json(response)
        except Exception as e:
            logger.error(f"LLM JSON调用失败: {e}")
            raise
    
    # ===== 同步方法 =====
    
    def chat_sync(self, messages: List[Dict[str, str]], temperature: float = 0.7,
                  max_tokens: int = 2000, response_format: Optional[Dict] = None) -> str:
        """发送聊天请求（同步）"""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    future = pool.submit(asyncio.run, self.chat(messages, temperature, max_tokens, response_format))
                    return future.result()
            else:
                return loop.run_until_complete(self.chat(messages, temperature, max_tokens, response_format))
        except RuntimeError:
            return asyncio.run(self.chat(messages, temperature, max_tokens, response_format))
    
    def chat_json_sync(self, messages: List[Dict[str, str]], temperature: float = 0.3,
                       max_tokens: int = 2000, timeout: Optional[float] = None) -> Dict[str, Any]:
        """发送聊天请求并解析JSON响应（同步）"""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    future = pool.submit(asyncio.run, self.chat_json(messages, temperature, max_tokens, timeout))
                    return future.result()
            else:
                return loop.run_until_complete(self.chat_json(messages, temperature, max_tokens, timeout))
        except RuntimeError:
            return asyncio.run(self.chat_json(messages, temperature, max_tokens, timeout))
    
    # ===== 工具方法 =====
    
    def _extract_json(self, text: str) -> Dict[str, Any]:
        """从文本中提取JSON"""
        import re
        match = re.search(r'```json\s*(\{.*?\})\s*```', text, re.DOTALL)
        if match:
            return json.loads(match.group(1))
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            return json.loads(match.group(0))
        raise ValueError(f"无法从响应中提取JSON: {text[:200]}")
    
    def get_model_name(self) -> str:
        """获取模型名称"""
        return self.model


class QwenClient(LLMClient):
    """通义千问客户端
    
    支持标准 Base URL 和 Coding Plan 专属 Base URL。
    默认使用标准 URL，可通过 base_url 参数指定。
    """
    
    # 标准 Base URL
    STANDARD_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    # Coding Plan 套餐专属 Base URL
    CODING_PLAN_BASE_URL = "https://coding.dashscope.aliyuncs.com/v1"
    
    def __init__(self, api_key: str, model: str = "qwen-plus", base_url: str = None):
        # 如果 key 是 sk-sp- 开头（Coding Plan 套餐），自动使用专属 URL
        if base_url is None:
            if api_key and api_key.startswith("sk-sp-"):
                base_url = self.CODING_PLAN_BASE_URL
            else:
                base_url = self.STANDARD_BASE_URL
        super().__init__(
            api_key=api_key,
            model=model,
            base_url=base_url
        )


class OpenAIClient(LLMClient):
    """OpenAI客户端"""
    
    def __init__(self, api_key: str, model: str = "gpt-4"):
        super().__init__(api_key=api_key, model=model)


class MockClient(LLMClient):
    """Mock客户端 - 用于测试
    
    同步方法，根据 prompt 内容返回有意义的 mock 数据，
    使评测框架能够测试完整的业务逻辑链路。
    """
    
    def __init__(self):
        super().__init__(api_key="mock", model="mock")
    
    def chat(self, messages: List[Dict[str, str]], **kwargs) -> str:
        """返回mock响应（同步）"""
        logger.info("使用MockClient.chat")
        return json.dumps(self._generate_mock_response(messages))
    
    def chat_json(self, messages: List[Dict[str, str]], **kwargs) -> Dict[str, Any]:
        """返回mock JSON响应（同步）"""
        logger.info("使用MockClient.chat_json")
        return self._generate_mock_response(messages)
    
    # 异步版本也保留，供 async 上下文使用
    async def achat(self, messages: List[Dict[str, str]], **kwargs) -> str:
        """异步版本"""
        return self.chat(messages, **kwargs)
    
    async def achat_json(self, messages: List[Dict[str, str]], **kwargs) -> Dict[str, Any]:
        """异步版本"""
        return self.chat_json(messages, **kwargs)
    
    def chat_sync(self, messages: List[Dict[str, str]], **kwargs) -> str:
        """同步版本"""
        return self.chat(messages, **kwargs)
    
    def chat_json_sync(self, messages: List[Dict[str, str]], **kwargs) -> Dict[str, Any]:
        """同步版本"""
        return self.chat_json(messages, **kwargs)
    
    def chat_stream(self, messages: List[Dict[str, str]], **kwargs):
        """Mock流式：一次性返回完整响应"""
        logger.info("使用MockClient.chat_stream")
        yield json.dumps(self._generate_mock_response(messages), ensure_ascii=False)
    
    def _generate_mock_response(self, messages: List[Dict[str, str]]) -> Dict[str, Any]:
        """根据 prompt 内容生成有意义的 mock 数据"""
        # 合并所有消息内容用于判断
        full_text = " ".join(m.get("content", "") for m in messages)
        
        # 简历解析
        if "PARSE_RESUME" in full_text or "简历" in full_text and "解析" in full_text:
            return self._mock_resume_parse(full_text)
        
        # JD解析
        if "PARSE_JD" in full_text or "JD" in full_text and "解析" in full_text:
            return self._mock_jd_parse(full_text)
        
        # 岗位评分
        if "SCORE_JOB" in full_text or "评分" in full_text or "匹配" in full_text:
            return self._mock_job_score(full_text)
        
        # 简历优化
        if "OPTIMIZE_RESUME" in full_text or "优化" in full_text:
            return self._mock_resume_optimize(full_text)
        
        # 面试题生成
        if "GENERATE_QUESTIONS" in full_text or "面试题" in full_text:
            return self._mock_generate_questions(full_text)
        
        # 回答评估
        if "EVALUATE_ANSWER" in full_text or "评估回答" in full_text:
            return self._mock_evaluate_answer(full_text)
        
        # 默认响应
        return {"result": "mock response", "message": "MockClient默认响应"}
    
    def _mock_resume_parse(self, text: str) -> Dict:
        """模拟简历解析结果"""
        return {
            "name": "张三",
            "phone": "13800138000",
            "email": "zhangsan@example.com",
            "location": "杭州",
            "years_of_experience": 5,
            "educations": [
                {"school": "浙江工业大学", "degree": "本科", "major": "计算机科学与技术",
                 "start_date": "2017.09", "end_date": "2021.06"}
            ],
            "work_experiences": [
                {"company": "杭州某互联网科技有限公司", "position": "高级测试开发工程师",
                 "start_date": "2023.03", "end_date": "至今",
                 "description": "负责自动化测试框架设计与AI模型测试方案落地",
                 "achievements": ["搭建CI/CD测试流水线", "主导AI模型测试方案"]},
                {"company": "杭州某软件有限公司", "position": "测试开发工程师",
                 "start_date": "2021.07", "end_date": "2023.02",
                 "description": "负责Web和移动端自动化测试",
                 "achievements": ["搭建UI自动化测试框架"]}
            ],
            "projects": [
                {"name": "AI模型自动化测试平台", "role": "技术负责人",
                 "description": "设计并实现AI模型批量测试框架",
                 "technologies": ["Python", "pytest", "FastAPI", "Docker"],
                 "achievements": ["支持准确率、召回率、F1等指标自动化计算"]},
                {"name": "Web自动化测试框架", "role": "核心开发",
                 "description": "基于Selenium+pytest搭建Web UI自动化测试框架",
                 "technologies": ["Python", "Selenium", "pytest", "Jenkins"],
                 "achievements": ["实现PO模式"]}
            ],
            "skills": [
                {"name": "Python", "level": "精通", "category": "编程语言"},
                {"name": "pytest", "level": "精通", "category": "测试框架"},
                {"name": "Selenium", "level": "熟练", "category": "测试工具"},
                {"name": "Appium", "level": "熟练", "category": "测试工具"},
                {"name": "CI/CD", "level": "熟练", "category": "工程实践"},
                {"name": "Jenkins", "level": "熟练", "category": "CI/CD"},
                {"name": "GitLab CI", "level": "熟悉", "category": "CI/CD"},
                {"name": "Docker", "level": "熟悉", "category": "容器化"},
                {"name": "FastAPI", "level": "熟悉", "category": "后端框架"}
            ],
            "summary": "5年测试开发经验，专注于自动化测试和AI模型测试领域"
        }
    
    def _mock_jd_parse(self, text: str) -> Dict:
        """模拟JD解析结果"""
        return {
            "title": "AI测试开发工程师",
            "company": "某科技有限公司",
            "location": "杭州",
            "salary_min": 30,
            "salary_max": 50,
            "years_required": 3,
            "education_required": "本科",
            "requirements": [
                {"skill": "Python", "required": True, "years": 3, "level": "熟练"},
                {"skill": "pytest", "required": True, "years": 2, "level": "熟练"},
                {"skill": "AI模型测试", "required": True, "years": 1, "level": "了解"},
                {"skill": "自动化测试", "required": True, "years": 3, "level": "精通"},
                {"skill": "CI/CD", "required": False, "years": 1, "level": "熟悉"}
            ],
            "responsibilities": [
                "负责AI模型的测试方案设计与实施",
                "搭建和维护自动化测试框架",
                "参与CI/CD流水线建设",
                "进行测试结果分析和质量报告"
            ],
            "benefits": [
                {"category": "薪酬", "description": "13薪+年终奖"},
                {"category": "福利", "description": "五险一金"}
            ],
            "company_size": "100-500人",
            "industry": "人工智能"
        }
    
    def _mock_job_score(self, text: str) -> Dict:
        """模拟岗位评分结果"""
        return {
            "skill_score": 80,
            "experience_score": 75,
            "salary_score": 85,
            "stability_score": 90,
            "growth_score": 100,
            "matched_skills": ["Python", "pytest", "自动化测试", "CI/CD"],
            "missing_skills": ["AI模型测试"],
            "strengths": ["Python和pytest经验丰富", "自动化测试经验扎实", "岗位稳定性高"],
            "weaknesses": ["AI模型测试经验需加强"],
            "suggestions": ["补充AI模型测试相关知识", "了解主流AI测试框架"],
            "ai_advice": "整体匹配度较高，建议补充AI测试方面的经验"
        }
    
    def _mock_resume_optimize(self, text: str) -> Dict:
        """模拟简历优化结果"""
        return {
            "optimized_resume": "优化后的简历内容（Mock）",
            "changes": [
                {"section": "技能", "type": "enhance",
                 "before": "熟悉Python", "after": "精通Python，5年深度使用经验",
                 "reason": "强化技能描述，匹配JD要求"},
                {"section": "项目", "type": "add_keyword",
                 "before": "设计测试框架", "after": "设计AI模型自动化测试框架，支持CI/CD流水线",
                 "reason": "补充JD关键词"}
            ],
            "keywords_added": ["AI模型测试", "CI/CD", "自动化测试框架"],
            "coverage_rate": 85.0,
            "tips": ["建议补充AI测试相关项目经验"]
        }
    
    def _mock_generate_questions(self, text: str) -> Dict:
        """模拟面试题生成结果"""
        return {
            "technical_questions": [
                {"question": "请介绍pytest的核心功能和你在项目中如何使用它",
                 "skill": "pytest", "difficulty": "中等",
                 "key_points": ["fixture机制", "参数化测试", "插件生态"],
                 "reference_answer": "pytest通过fixture实现依赖注入..."},
                {"question": "如何设计AI模型的自动化测试方案？",
                 "skill": "AI模型测试", "difficulty": "困难",
                 "key_points": ["评估指标", "测试数据构造", "回归测试"],
                 "reference_answer": "AI模型测试需要关注准确率、召回率等指标..."},
                {"question": "请描述你搭建CI/CD测试流水线的经验",
                 "skill": "CI/CD", "difficulty": "中等",
                 "key_points": ["Jenkins/GitLab CI", "自动化触发", "测试报告"],
                 "reference_answer": "我使用Jenkins搭建了完整的CI/CD流水线..."}
            ],
            "behavioral_questions": [
                {"question": "请描述一个你解决过的最复杂的技术问题",
                 "competency": "问题解决能力",
                 "star_guide": "Situation: 描述背景, Task: 你的任务, Action: 采取的行动, Result: 最终结果"},
                {"question": "请举例说明你如何在团队中发挥作用",
                 "competency": "团队协作",
                 "star_guide": "Situation: 项目背景, Task: 你的角色, Action: 具体贡献, Result: 团队成果"}
            ]
        }
    
    def _mock_evaluate_answer(self, text: str) -> Dict:
        """模拟回答评估结果"""
        return {
            "score": 78,
            "completeness": 80,
            "accuracy": 75,
            "star_usage": 70,
            "quantification": 65,
            "expression": 85,
            "strengths": ["回答结构清晰", "涵盖了关键技术点"],
            "weaknesses": ["缺少具体量化数据", "STAR法则运用不够充分"],
            "improvements": ["补充具体的项目数据", "使用STAR法则组织回答",
                           "增加技术细节的深度"],
            "reference_answer": "建议结合具体项目经验，按照STAR法则组织回答..."
        }


class LLMClientFactory:
    """LLM客户端工厂"""
    
    @staticmethod
    def create(provider: str = None, model: str = None, api_key: str = None) -> LLMClient:
        """创建LLM客户端"""
        provider = provider or settings.llm_provider
        api_key = api_key or (settings.qwen_api_key if provider == "qwen" else settings.openai_api_key)
        
        if provider == "qwen":
            model = model or settings.qwen_model
            return QwenClient(api_key=api_key, model=model)
        elif provider == "openai":
            model = model or settings.openai_model
            return OpenAIClient(api_key=api_key, model=model)
        elif provider == "mock":
            return MockClient()
        else:
            raise ValueError(f"不支持的LLM提供商: {provider}")


# 全局客户端实例
_llm_client: Optional[LLMClient] = None


def get_llm_client() -> LLMClient:
    """获取全局LLM客户端"""
    global _llm_client
    if _llm_client is None:
        _llm_client = LLMClientFactory.create()
    return _llm_client


def set_llm_client(client: LLMClient):
    """设置全局LLM客户端"""
    global _llm_client
    _llm_client = client
