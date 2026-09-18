"""数据模型 - 按SDD文档设计"""
from app.models.resume import (
    ResumeData,
    Education,
    WorkExperience,
    Project,
    Skill,
    ResumeCreate,
    ResumeResponse,
)
from app.models.job import (
    JobData,
    JobRequirement,
    JobBenefit,
    JobCreate,
    JobResponse,
)
from app.models.score import (
    ScoreResult,
    ScoreDetail,
    SkillMatch,
    ScoreRequest,
    ScoreResponse,
)
from app.models.conversation import (
    CardType,
    Message,
    RichCard,
    ScoreCardData,
    DiffItem,
    DiffCardData,
    QuestionCardData,
    ProgressCardData,
    ConversationCreate,
    ConversationResponse,
    ChatRequest,
    ChatResponse,
)
from app.models.application import (
    ApplicationStatus,
    ApplicationCreate,
    ApplicationUpdate,
    ApplicationResponse,
    ApplicationStats,
    DailyProgress,
)
from app.models.settings import (
    UserPreferences,
    SettingsUpdate,
)

__all__ = [
    # Resume
    "ResumeData",
    "Education",
    "WorkExperience",
    "Project",
    "Skill",
    "ResumeCreate",
    "ResumeResponse",
    # Job
    "JobData",
    "JobRequirement",
    "JobBenefit",
    "JobCreate",
    "JobResponse",
    # Score
    "ScoreResult",
    "ScoreDetail",
    "SkillMatch",
    "ScoreRequest",
    "ScoreResponse",
    # Conversation
    "CardType",
    "Message",
    "RichCard",
    "ScoreCardData",
    "DiffItem",
    "DiffCardData",
    "QuestionCardData",
    "ProgressCardData",
    "ConversationCreate",
    "ConversationResponse",
    "ChatRequest",
    "ChatResponse",
    # Application
    "ApplicationStatus",
    "ApplicationCreate",
    "ApplicationUpdate",
    "ApplicationResponse",
    "ApplicationStats",
    "DailyProgress",
    # Settings
    "UserPreferences",
    "SettingsUpdate",
]
