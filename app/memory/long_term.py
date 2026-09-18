"""长期记忆模块 - 跨会话持久化存储

负责存储用户画像、偏好、历史操作摘要等长期信息。
骨架阶段使用JSON文件存储，后续可扩展为向量数据库。
"""
import json
from typing import Dict, List, Optional, Any
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, field, asdict
from loguru import logger


@dataclass
class UserProfile:
    """用户画像"""
    name: str = ""
    phone: str = ""
    email: str = ""
    skills: List[str] = field(default_factory=list)
    education: List[Dict] = field(default_factory=list)
    work_experience: List[Dict] = field(default_factory=list)
    project_experience: List[Dict] = field(default_factory=list)
    updated_at: str = ""


@dataclass
class UserPreferences:
    """用户偏好"""
    target_city: str = "杭州"
    expected_salary_min: int = 270000
    target_positions: List[str] = field(default_factory=list)
    excluded_keywords: List[str] = field(default_factory=list)
    updated_at: str = ""


@dataclass
class OperationSummary:
    """操作摘要（用于长期记忆）"""
    operation_type: str    # resume_parse / job_score / interview 等
    summary: str           # 操作摘要
    result: str            # 关键结果
    timestamp: str = ""


class LongTermMemory:
    """长期记忆（跨会话持久化）"""
    
    def __init__(self, storage_path: str = "./data/memory"):
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)
        
        self.user_profile: UserProfile = UserProfile()
        self.preferences: UserPreferences = UserPreferences()
        self.operation_history: List[OperationSummary] = []
        
        # 从磁盘加载
        self._load()
        logger.info(f"长期记忆初始化，存储路径: {self.storage_path}")
    
    def update_profile(self, profile_data: Dict):
        """更新用户画像（从简历解析结果中提取）"""
        for key, value in profile_data.items():
            if hasattr(self.user_profile, key):
                setattr(self.user_profile, key, value)
        
        self.user_profile.updated_at = datetime.now().isoformat()
        self._save_profile()
        logger.info(f"更新用户画像: {self.user_profile.name}")
    
    def update_preferences(self, prefs_data: Dict):
        """更新用户偏好"""
        for key, value in prefs_data.items():
            if hasattr(self.preferences, key):
                setattr(self.preferences, key, value)
        
        self.preferences.updated_at = datetime.now().isoformat()
        self._save_preferences()
        logger.info("更新用户偏好")
    
    def add_operation(self, op_type: str, summary: str, result: str):
        """添加操作摘要"""
        op = OperationSummary(
            operation_type=op_type,
            summary=summary,
            result=result,
            timestamp=datetime.now().isoformat()
        )
        self.operation_history.append(op)
        
        # 保留最近100条
        if len(self.operation_history) > 100:
            self.operation_history = self.operation_history[-100:]
        
        self._save_history()
        logger.debug(f"添加操作摘要: {op_type}")
    
    def get_profile(self) -> UserProfile:
        """获取用户画像"""
        return self.user_profile
    
    def get_preferences(self) -> UserPreferences:
        """获取用户偏好"""
        return self.preferences
    
    def get_recent_operations(self, n: int = 10) -> List[OperationSummary]:
        """获取最近n条操作摘要"""
        return self.operation_history[-n:]
    
    def search_operations(self, keyword: str) -> List[OperationSummary]:
        """搜索操作历史"""
        results = []
        for op in self.operation_history:
            if keyword.lower() in op.summary.lower() or keyword.lower() in op.result.lower():
                results.append(op)
        return results
    
    def get_context_for_llm(self) -> str:
        """获取供LLM使用的上下文信息"""
        context_parts = []
        
        # 用户画像摘要
        if self.user_profile.name:
            context_parts.append(f"用户姓名: {self.user_profile.name}")
        if self.user_profile.skills:
            context_parts.append(f"技能: {', '.join(self.user_profile.skills[:10])}")
        
        # 用户偏好
        if self.preferences.target_city:
            context_parts.append(f"目标城市: {self.preferences.target_city}")
        if self.preferences.target_positions:
            context_parts.append(f"目标岗位: {', '.join(self.preferences.target_positions)}")
        if self.preferences.expected_salary_min:
            context_parts.append(f"期望薪资: >= {self.preferences.expected_salary_min}")
        
        return "\n".join(context_parts) if context_parts else ""
    
    def clear(self):
        """清空长期记忆"""
        self.user_profile = UserProfile()
        self.preferences = UserPreferences()
        self.operation_history = []
        self._save_all()
        logger.warning("长期记忆已清空")
    
    # ============ 记忆观测（Memory Span，指南 1.2） ============
    
    def _observe_io(self, op: str, fname: str, error: Optional[Exception] = None) -> None:
        """load/save 观测：memory span；失败抛对应 flag（静默降级，不影响主链路）"""
        try:
            from app.observability import memory_guard as mg
            if error is None:
                mg.record_memory_span(op, "long_term", file=fname)
            else:
                mg.record_memory_span(op, "long_term", success=False,
                                      file=fname, error=str(error))
                mg.flag_memory("long_term_load_corrupt" if op == "load" else "long_term_save_failed",
                               detail=f"{fname}: {error}")
        except Exception:
            pass
    
    # ============ 持久化方法 ============
    
    def _load(self):
        """从磁盘加载"""
        self._load_profile()
        self._load_preferences()
        self._load_history()
    
    def _load_profile(self):
        """加载用户画像（损坏时降级为默认值并抛 flag，不阻断启动）"""
        file_path = self.storage_path / "user_profile.json"
        if not file_path.exists():
            return
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                self.user_profile = UserProfile(**data)
        except Exception as e:
            logger.error(f"长期记忆用户画像加载失败(降级为默认值): {e}")
            self._observe_io("load", file_path.name, e)
    
    def _load_preferences(self):
        """加载用户偏好（损坏时降级为默认值并抛 flag）"""
        file_path = self.storage_path / "user_preferences.json"
        if not file_path.exists():
            return
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                self.preferences = UserPreferences(**data)
        except Exception as e:
            logger.error(f"长期记忆用户偏好加载失败(降级为默认值): {e}")
            self._observe_io("load", file_path.name, e)
    
    def _load_history(self):
        """加载操作历史（损坏时降级为空列表并抛 flag）"""
        file_path = self.storage_path / "operation_history.json"
        if not file_path.exists():
            return
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                self.operation_history = [OperationSummary(**item) for item in data]
        except Exception as e:
            logger.error(f"长期记忆操作历史加载失败(降级为空): {e}")
            self._observe_io("load", file_path.name, e)
    
    def _save_profile(self):
        """保存用户画像"""
        file_path = self.storage_path / "user_profile.json"
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(asdict(self.user_profile), f, ensure_ascii=False, indent=2)
            self._observe_io("save", file_path.name)
        except Exception as e:
            logger.error(f"长期记忆用户画像保存失败: {e}")
            self._observe_io("save", file_path.name, e)
    
    def _save_preferences(self):
        """保存用户偏好"""
        file_path = self.storage_path / "user_preferences.json"
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(asdict(self.preferences), f, ensure_ascii=False, indent=2)
            self._observe_io("save", file_path.name)
        except Exception as e:
            logger.error(f"长期记忆用户偏好保存失败: {e}")
            self._observe_io("save", file_path.name, e)
    
    def _save_history(self):
        """保存操作历史"""
        file_path = self.storage_path / "operation_history.json"
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump([asdict(op) for op in self.operation_history], f, ensure_ascii=False, indent=2)
            self._observe_io("save", file_path.name)
        except Exception as e:
            logger.error(f"长期记忆操作历史保存失败: {e}")
            self._observe_io("save", file_path.name, e)
    
    def _save_all(self):
        """保存所有"""
        self._save_profile()
        self._save_preferences()
        self._save_history()
