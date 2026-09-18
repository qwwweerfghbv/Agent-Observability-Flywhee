"""短期记忆模块 - 当前对话上下文管理

负责管理单次会话内的消息历史，支持上下文窗口裁剪。
"""
from typing import List, Dict, Optional
from dataclasses import dataclass, field
from datetime import datetime
from loguru import logger


@dataclass
class Message:
    """消息"""
    role: str           # user / assistant / tool / system
    content: str
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict = field(default_factory=dict)
    token_count: int = 0  # 估算的token数


class ShortTermMemory:
    """短期记忆（当前对话上下文）"""
    
    def __init__(self, max_messages: int = 20, max_tokens: int = 4000):
        self.max_messages = max_messages
        self.max_tokens = max_tokens
        self._messages: List[Message] = []
        self._system_prompt: Optional[str] = None
        # 记忆观测计数（Memory Span 数据源，指南 1.2/5.3）
        self.added_count = 0      # 累计写入消息数
        self.trim_count = 0       # 累计窗口裁剪消息数（压缩频繁判据）
        self._trim_flagged = False
        logger.debug(f"短期记忆初始化: max_messages={max_messages}, max_tokens={max_tokens}")
    
    def set_system_prompt(self, prompt: str):
        """设置系统Prompt"""
        self._system_prompt = prompt
        logger.debug("设置系统Prompt")
    
    def add_message(self, role: str, content: str, metadata: Dict = None):
        """添加消息"""
        msg = Message(
            role=role,
            content=content,
            metadata=metadata or {},
            token_count=self._estimate_tokens(content)
        )
        self._messages.append(msg)
        self.added_count += 1
        
        # 超出窗口时裁剪
        self._trim_if_needed()
        logger.debug(f"添加消息: role={role}, tokens={msg.token_count}")
    
    def get_messages(self) -> List[Dict]:
        """获取消息列表（LLM调用格式）"""
        messages = []
        
        # 系统Prompt始终在最前面
        if self._system_prompt:
            messages.append({"role": "system", "content": self._system_prompt})
        
        # 历史消息
        for msg in self._messages:
            messages.append({
                "role": msg.role,
                "content": msg.content,
            })
        
        return messages
    
    def get_recent_messages(self, n: int = 5) -> List[Dict]:
        """获取最近n条消息"""
        recent = self._messages[-n:] if n <= len(self._messages) else self._messages
        return [{"role": m.role, "content": m.content} for m in recent]
    
    def get_token_count(self) -> int:
        """获取当前总token数"""
        total = sum(m.token_count for m in self._messages)
        if self._system_prompt:
            total += self._estimate_tokens(self._system_prompt)
        return total
    
    def clear(self):
        """清空消息（保留系统Prompt）"""
        self._messages.clear()
        logger.debug("短期记忆已清空")
    
    def get_message_count(self) -> int:
        """获取消息数量"""
        return len(self._messages)
    
    def health(self) -> Dict:
        """记忆健康快照（Memory Span 观测用）"""
        return {
            "msg_count": len(self._messages),
            "token_count": self.get_token_count(),
            "max_messages": self.max_messages,
            "max_tokens": self.max_tokens,
            "added_count": self.added_count,
            "trim_count": self.trim_count,
            "over_token_window": self.get_token_count() > self.max_tokens,
        }
    
    def _observe_trim(self, removed: int) -> None:
        """裁剪观测：memory span + 压缩频繁 flag（静默降级，不影响主链路）"""
        try:
            from app.observability import memory_guard as mg
            mg.record_memory_span("trim", "short_term", trimmed=removed,
                                  trim_total=self.trim_count,
                                  msg_count=len(self._messages),
                                  token_count=self.get_token_count())
            if self.trim_count >= mg.TRIM_FREQUENT_THRESHOLD and not self._trim_flagged:
                self._trim_flagged = True
                mg.flag_memory("short_term_trim_frequent",
                               detail=f"累计裁剪{self.trim_count}条"
                                      f"(阈值{mg.TRIM_FREQUENT_THRESHOLD})")
        except Exception:
            pass
    
    def _trim_if_needed(self):
        """如果超出窗口，裁剪旧消息"""
        removed_count = 0
        # 按消息数裁剪
        while len(self._messages) > self.max_messages:
            removed = self._messages.pop(0)
            removed_count += 1
            logger.debug(f"裁剪消息: role={removed.role}, tokens={removed.token_count}")
        
        # 按token数裁剪（保留至少1条）
        while self.get_token_count() > self.max_tokens and len(self._messages) > 1:
            removed = self._messages.pop(0)
            removed_count += 1
            logger.debug(f"裁剪消息(token): role={removed.role}, tokens={removed.token_count}")
        
        if removed_count:
            self.trim_count += removed_count
            self._observe_trim(removed_count)
    
    @staticmethod
    def _estimate_tokens(text: str) -> int:
        """估算token数（中文约1.5字/token，英文约4字符/token）"""
        if not text:
            return 0
        # 简单估算：中文按1.5字/token，其他按4字符/token
        chinese_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
        other_chars = len(text) - chinese_chars
        return int(chinese_chars / 1.5 + other_chars / 4)
