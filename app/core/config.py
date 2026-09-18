"""配置管理模块"""
from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    """应用配置"""
    
    # LLM配置
    llm_provider: str = "qwen"
    qwen_api_key: str = ""
    qwen_model: str = "qwen-plus"
    openai_api_key: str = ""
    openai_model: str = "gpt-4"
    
    # 数据库配置
    database_url: str = "sqlite+aiosqlite:///./data/job_agent.db"
    
    # 应用配置
    app_env: str = "development"
    log_level: str = "INFO"
    max_llm_turns: int = 20
    llm_timeout: int = 30
    
    # 用户偏好
    target_city: str = "杭州"
    expected_salary_min: int = 270000
    target_positions: List[str] = ["AI测试开发", "AI Agent评测"]
    
    class Config:
        env_file = ".env"
        case_sensitive = False


# 全局配置实例
settings = Settings()
