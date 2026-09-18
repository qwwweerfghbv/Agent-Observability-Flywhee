"""对话相关数据模型 - SDD"""
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum


class CardType(str, Enum):
    """富卡片类型"""
    SCORE = "score_card"           # 评分卡片
    DIFF = "diff_card"             # Diff卡片
    QUESTION = "question_card"     # 题目卡片
    INTERVIEW = "interview_card"   # 面试对话卡片
    PROGRESS = "progress_card"     # 进度卡片
    RECOMMEND = "recommend_card"   # 岗位推荐卡片


class Message(BaseModel):
    """对话消息"""
    role: str = Field(..., description="角色: user/assistant/system")
    content: str = Field(..., description="文本内容")
    cards: List[Dict[str, Any]] = Field(default_factory=list, description="富卡片列表")
    timestamp: datetime = Field(default_factory=datetime.now)
    metadata: Dict[str, Any] = Field(default_factory=dict, description="额外信息")


class RichCard(BaseModel):
    """富卡片基类"""
    type: CardType
    data: Dict[str, Any]


class ScoreCardData(BaseModel):
    """评分卡片数据"""
    total_score: float = Field(..., description="综合评分")
    score_level: str = Field(..., description="评分等级: A/B/C/D")
    dimensions: Dict[str, float] = Field(..., description="各维度评分")
    strengths: List[str] = Field(default_factory=list, description="优势")
    weaknesses: List[str] = Field(default_factory=list, description="不足")
    suggestions: List[str] = Field(default_factory=list, description="建议")
    stability_signals: Dict[str, Any] = Field(default_factory=dict, description="稳定性信号")
    ai_replacement_risk: int = Field(default=50, description="AI替代风险(0-100)")


class DiffItem(BaseModel):
    """Diff修改项"""
    section: str = Field(..., description="修改部分（技能/项目/自我评价）")
    before: str = Field(..., description="修改前")
    after: str = Field(..., description="修改后")
    reason: str = Field(..., description="修改原因")
    confirmed: Optional[bool] = Field(None, description="用户是否已确认")


class DiffCardData(BaseModel):
    """Diff卡片数据"""
    items: List[DiffItem] = Field(default_factory=list, description="修改列表")
    total_changes: int = Field(..., description="总修改数")
    confirmed_count: int = Field(default=0, description="已确认数")


class QuestionCardData(BaseModel):
    """题目卡片数据"""
    interview_type: str = Field(..., description="面试类型: technical/behavioral/hr")
    questions: List[Dict[str, Any]] = Field(default_factory=list, description="题目列表")


class ProgressCardData(BaseModel):
    """进度卡片数据"""
    daily_target: int = Field(..., description="每日目标")
    applied_today: int = Field(..., description="今日已投递")
    remaining: int = Field(..., description="还需投递")
    encouragement: str = Field(default="", description="鼓励语")


class ConversationCreate(BaseModel):
    """创建对话请求"""
    title: Optional[str] = Field(None, description="对话标题")


class ConversationResponse(BaseModel):
    """对话响应"""
    id: int
    title: str
    message_count: int
    context_job_id: Optional[int] = None
    context_resume_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class ConversationDetail(ConversationResponse):
    """对话详情：在 ConversationResponse 基础上附带完整消息历史，供前端切换会话复原。

    message_count 放宽为可选（默认 0）：get_conversation 服务返回中含 messages 但无
    message_count，由 API 层按 messages 长度派生回填，避免响应校验失败（原 ConversationResponse
    必填 message_count 会导致 GET /conversations/{id} 抛 ResponseValidationError → 500）。
    """
    message_count: int = 0
    messages: List[Dict[str, Any]] = Field(default_factory=list)


class ChatRequest(BaseModel):
    """对话请求"""
    conversation_id: Optional[int] = Field(None, description="对话ID，为空则创建新对话")
    message: str = Field(..., description="用户消息")
    image_paths: Optional[List[str]] = Field(None, description="上传图片路径列表（最多10张）")
    file_paths: Optional[List[str]] = Field(None, description="上传文件路径列表")


class ChatResponse(BaseModel):
    """对话响应"""
    conversation_id: int
    reply: Message
    context_job_id: Optional[int] = None
    context_resume_id: Optional[int] = None
