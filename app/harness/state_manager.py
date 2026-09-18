"""状态管理模块 - 会话持久化、断点恢复、会话分叉"""
import json
from typing import Dict, Optional, List
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, field, asdict
from loguru import logger


@dataclass
class SessionContext:
    """会话上下文"""
    session_id: str
    task: str = ""
    messages: List[Dict] = field(default_factory=list)
    tool_results: List[Dict] = field(default_factory=list)
    metadata: Dict = field(default_factory=dict)
    is_completed: bool = False
    created_at: str = ""
    updated_at: str = ""


class StateManager:
    """状态管理器"""
    
    def __init__(self, storage_path: str = "./data/sessions"):
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self._active_sessions: Dict[str, SessionContext] = {}
        logger.info(f"状态管理器初始化，存储路径: {self.storage_path}")
    
    def load_or_init(self, session_id: str, task: str = "") -> SessionContext:
        """加载已有会话或初始化新会话"""
        # 检查内存缓存
        if session_id in self._active_sessions:
            logger.debug(f"从缓存加载会话: {session_id}")
            return self._active_sessions[session_id]
        
        # 尝试从磁盘恢复
        file_path = self.storage_path / f"{session_id}.json"
        if file_path.exists():
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                session = SessionContext(**data)
                self._active_sessions[session_id] = session
                logger.info(f"从磁盘恢复会话: {session_id}, 消息数: {len(session.messages)}")
                return session
        
        # 新建会话
        now = datetime.now().isoformat()
        session = SessionContext(
            session_id=session_id,
            task=task,
            created_at=now,
            updated_at=now
        )
        self._active_sessions[session_id] = session
        logger.info(f"创建新会话: {session_id}")
        return session
    
    def save(self, session_id: str, context: SessionContext = None):
        """持久化会话状态"""
        if context is None:
            context = self._active_sessions.get(session_id)
        
        if context is None:
            logger.warning(f"会话不存在: {session_id}")
            return
        
        context.updated_at = datetime.now().isoformat()
        file_path = self.storage_path / f"{session_id}.json"
        
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(asdict(context), f, ensure_ascii=False, indent=2)
        
        logger.debug(f"保存会话: {session_id}")
    
    def add_message(self, session_id: str, role: str, content: str, metadata: Dict = None):
        """添加消息到会话"""
        context = self.load_or_init(session_id)
        message = {
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat()
        }
        if metadata:
            message["metadata"] = metadata
        
        context.messages.append(message)
        logger.debug(f"添加消息: session={session_id}, role={role}")
    
    def add_tool_result(self, session_id: str, tool_name: str, result: Dict):
        """添加工具执行结果"""
        context = self.load_or_init(session_id)
        tool_result = {
            "tool_name": tool_name,
            "result": result,
            "timestamp": datetime.now().isoformat()
        }
        context.tool_results.append(tool_result)
        logger.debug(f"添加工具结果: session={session_id}, tool={tool_name}")
    
    def fork_session(self, session_id: str, new_session_id: str) -> SessionContext:
        """会话分叉（fork）"""
        original = self.load_or_init(session_id)
        
        now = datetime.now().isoformat()
        forked = SessionContext(
            session_id=new_session_id,
            task=original.task,
            messages=original.messages.copy(),
            tool_results=original.tool_results.copy(),
            metadata={**original.metadata, "forked_from": session_id},
            created_at=now,
            updated_at=now
        )
        
        self._active_sessions[new_session_id] = forked
        logger.info(f"会话分叉: {session_id} -> {new_session_id}")
        return forked
    
    def clear_session(self, session_id: str):
        """清除会话"""
        if session_id in self._active_sessions:
            del self._active_sessions[session_id]
        
        file_path = self.storage_path / f"{session_id}.json"
        if file_path.exists():
            file_path.unlink()
            logger.info(f"清除会话: {session_id}")
    
    def list_sessions(self) -> List[str]:
        """列出所有会话"""
        sessions = set(self._active_sessions.keys())
        
        # 从文件系统加载
        for file in self.storage_path.glob("*.json"):
            sessions.add(file.stem)
        
        return list(sessions)
    
    def get_context_messages(self, session_id: str, max_count: int = 10) -> List[Dict]:
        """获取上下文消息（用于LLM调用）"""
        context = self.load_or_init(session_id)
        messages = context.messages[-max_count * 2:]  # 取最近的消息
        return [{"role": m["role"], "content": m["content"]} for m in messages]
