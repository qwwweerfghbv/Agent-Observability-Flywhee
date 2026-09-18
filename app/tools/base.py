"""工具基类模块"""
from abc import ABC, abstractmethod
from typing import Any, Dict
from pydantic import BaseModel


class BaseTool(ABC):
    """工具基类"""
    name: str = ""
    description: str = ""
    input_schema: type(BaseModel) = None
    
    @abstractmethod
    def run(self, **kwargs) -> Any:
        """执行工具逻辑"""
        pass
    
    def get_schema(self) -> Dict:
        """获取工具的JSON Schema，供LLM调用"""
        schema = {
            "name": self.name,
            "description": self.description,
        }
        if self.input_schema:
            schema["parameters"] = self.input_schema.schema()
        return schema
