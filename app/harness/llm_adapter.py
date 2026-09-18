"""LLM适配器模块 - 可插拔的LLM调用封装"""
from abc import ABC, abstractmethod
from typing import List, Dict, Optional
from dataclasses import dataclass, field
from loguru import logger


@dataclass
class LLMResponse:
    """LLM响应标准格式"""
    content: str
    tool_calls: List[Dict] = field(default_factory=list)
    usage: Dict = field(default_factory=dict)
    
    def has_tool_calls(self) -> bool:
        return bool(self.tool_calls)


class BaseLLMAdapter(ABC):
    """LLM适配器基类（可插拔）"""
    
    @abstractmethod
    def chat(self, messages: List[Dict], tools: List[Dict] = None) -> LLMResponse:
        """调用LLM"""
        pass
    
    @abstractmethod
    def get_model_name(self) -> str:
        """获取模型名称"""
        pass


class MockLLMAdapter(BaseLLMAdapter):
    """Mock LLM适配器（用于测试和骨架验证）"""
    
    def __init__(self, model: str = "mock-model"):
        self.model = model
        logger.info(f"初始化MockLLMAdapter: {model}")
    
    def chat(self, messages: List[Dict], tools: List[Dict] = None) -> LLMResponse:
        """模拟LLM响应"""
        logger.debug(f"MockLLM调用，消息数: {len(messages)}")
        
        # 检查是否有工具可用
        if tools and len(tools) > 0:
            # 模拟工具调用
            return LLMResponse(
                content="我将使用工具来处理这个请求",
                tool_calls=[{
                    "name": tools[0]["name"],
                    "arguments": {"input": "mock_input"}
                }],
                usage={"prompt_tokens": 100, "completion_tokens": 50}
            )
        else:
            # 模拟普通回复
            return LLMResponse(
                content="这是一个Mock响应，用于骨架验证。",
                usage={"prompt_tokens": 50, "completion_tokens": 20}
            )
    
    def get_model_name(self) -> str:
        return f"mock-{self.model}"


class QwenAdapter(BaseLLMAdapter):
    """通义千问适配器"""
    
    def __init__(self, api_key: str, model: str = "qwen-plus"):
        self.api_key = api_key
        self.model = model
        # TODO: 初始化通义千问客户端
        logger.info(f"初始化QwenAdapter: {model}")
    
    def chat(self, messages: List[Dict], tools: List[Dict] = None) -> LLMResponse:
        """调用通义千问"""
        # TODO: 实现通义千问API调用
        raise NotImplementedError("QwenAdapter.chat 尚未实现，请配置API Key后使用")
    
    def get_model_name(self) -> str:
        return f"qwen-{self.model}"


class OpenAIAdapter(BaseLLMAdapter):
    """OpenAI适配器"""
    
    def __init__(self, api_key: str, model: str = "gpt-4"):
        self.api_key = api_key
        self.model = model
        # TODO: 初始化OpenAI客户端
        logger.info(f"初始化OpenAIAdapter: {model}")
    
    def chat(self, messages: List[Dict], tools: List[Dict] = None) -> LLMResponse:
        """调用OpenAI"""
        # TODO: 实现OpenAI API调用
        raise NotImplementedError("OpenAIAdapter.chat 尚未实现，请配置API Key后使用")
    
    def get_model_name(self) -> str:
        return self.model


class LLMAdapterFactory:
    """LLM适配器工厂（可插拔切换）"""
    
    _adapters = {
        "mock": MockLLMAdapter,
        "qwen": QwenAdapter,
        "openai": OpenAIAdapter,
    }
    
    @classmethod
    def create(cls, provider: str, **kwargs) -> BaseLLMAdapter:
        """创建LLM适配器"""
        adapter_class = cls._adapters.get(provider)
        if not adapter_class:
            raise ValueError(f"不支持的LLM提供商: {provider}，可选: {list(cls._adapters.keys())}")
        return adapter_class(**kwargs)
    
    @classmethod
    def register(cls, name: str, adapter_class):
        """注册新的LLM适配器"""
        cls._adapters[name] = adapter_class
        logger.info(f"注册新LLM适配器: {name}")
