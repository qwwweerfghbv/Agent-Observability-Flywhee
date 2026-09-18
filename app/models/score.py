"""评分数据模型"""
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime


class SkillMatch(BaseModel):
    """技能匹配详情"""
    skill: str = Field(..., description="技能名称")
    matched: bool = Field(..., description="是否匹配")
    resume_level: str = Field("", description="简历中的熟练度")
    job_level: str = Field("", description="JD要求的熟练度")
    score: float = Field(0, description="该技能得分")


class ScoreDetail(BaseModel):
    """评分详情"""
    # 各维度得分（0-100）
    skill_score: float = Field(0, description="技能匹配度得分")
    experience_score: float = Field(0, description="经验匹配度得分")
    salary_score: float = Field(0, description="薪资匹配度得分")
    stability_score: float = Field(0, description="岗位稳定性得分（公司稳定性+岗位核心度+AI替代风险）")
    growth_score: float = Field(0, description="发展前景得分（行业趋势+岗位前景）")
    
    # 技能匹配详情
    skill_matches: List[SkillMatch] = Field(default_factory=list)
    matched_skills: List[str] = Field(default_factory=list)
    missing_skills: List[str] = Field(default_factory=list)
    
    # 权重配置
    skill_weight: float = Field(0.30, description="技能权重")
    experience_weight: float = Field(0.20, description="经验权重")
    salary_weight: float = Field(0.15, description="薪资权重")
    stability_weight: float = Field(0.25, description="稳定性权重")
    growth_weight: float = Field(0.10, description="发展前景权重")


class ScoreResult(BaseModel):
    """评分结果"""
    resume_id: int = Field(..., description="简历ID")
    job_id: int = Field(..., description="岗位ID")
    
    # 综合得分
    total_score: float = Field(0, description="综合得分（0-100）")
    score_level: str = Field("", description="评分等级：A/B/C/D")
    
    # 详细得分
    detail: ScoreDetail = Field(default_factory=ScoreDetail)
    
    # AI建议
    ai_advice: str = Field("", description="AI综合建议")
    strengths: List[str] = Field(default_factory=list, description="优势点")
    weaknesses: List[str] = Field(default_factory=list, description="不足点")
    suggestions: List[str] = Field(default_factory=list, description="改进建议")
    
    # 元数据
    created_at: datetime = Field(default_factory=datetime.now)
    
    def get_score_level(self) -> str:
        """根据分数计算等级"""
        if self.total_score >= 85:
            return "A"
        elif self.total_score >= 70:
            return "B"
        elif self.total_score >= 55:
            return "C"
        else:
            return "D"
    
    def calculate_total(self) -> float:
        """计算加权总分"""
        d = self.detail
        total = (
            d.skill_score * d.skill_weight +
            d.experience_score * d.experience_weight +
            d.salary_score * d.salary_weight +
            d.stability_score * d.stability_weight +
            d.growth_score * d.growth_weight
        )
        self.total_score = round(total, 2)
        self.score_level = self.get_score_level()
        return self.total_score


class ScoreRequest(BaseModel):
    """评分请求"""
    resume_id: int = Field(..., description="简历ID")
    job_id: int = Field(..., description="岗位ID")
    custom_weights: Optional[dict] = Field(None, description="自定义权重")


class ScoreResponse(BaseModel):
    """评分响应"""
    result: ScoreResult
    resume_summary: str = ""
    job_summary: str = ""
