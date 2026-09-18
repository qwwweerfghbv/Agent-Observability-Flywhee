"""岗位数据模型"""
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime


class JobRequirement(BaseModel):
    """岗位要求"""
    skill: str = Field(..., description="技能要求")
    required: bool = Field(True, description="是否必须")
    years: Optional[float] = Field(None, description="要求年限")
    level: str = Field("", description="要求熟练度：了解/熟悉/掌握/精通")


class JobBenefit(BaseModel):
    """岗位福利"""
    category: str = Field(..., description="福利类别：薪资/假期/成长/其他")
    description: str = Field(..., description="福利描述")


class JobData(BaseModel):
    """岗位结构化数据"""
    # 基本信息
    title: str = Field(..., description="岗位名称")
    company: str = Field("", description="公司名称")
    location: str = Field("", description="工作地点")
    salary_min: float = Field(0, description="最低薪资（年薪，万）")
    salary_max: float = Field(0, description="最高薪资（年薪，万）")
    
    # 岗位要求
    years_required: int = Field(0, description="要求工作年限")
    education_required: str = Field("本科", description="学历要求")
    requirements: List[JobRequirement] = Field(default_factory=list, description="技能要求列表")
    
    # 岗位职责
    responsibilities: List[str] = Field(default_factory=list, description="岗位职责")
    
    # 福利
    benefits: List[JobBenefit] = Field(default_factory=list, description="福利待遇")
    
    # 公司信息
    company_size: str = Field("", description="公司规模")
    industry: str = Field("", description="所属行业")
    company_description: str = Field("", description="公司简介")
    
    # 来源
    source_url: str = Field("", description="来源链接")
    source_platform: str = Field("", description="来源平台")
    
    # 原始文本
    raw_text: str = Field("", description="JD原始文本")
    
    # 稳定性信号
    stability_signals: Optional[dict] = Field(None, description="稳定性评估信号")
    
    # 元数据
    created_at: datetime = Field(default_factory=datetime.now)
    
    def get_required_skills(self) -> List[str]:
        """获取必须技能"""
        return [r.skill for r in self.requirements if r.required]
    
    def get_all_skills(self) -> List[str]:
        """获取所有技能"""
        return [r.skill for r in self.requirements]
    
    def get_keywords(self) -> List[str]:
        """获取JD关键词"""
        keywords = set()
        keywords.add(self.title)
        for r in self.requirements:
            keywords.add(r.skill)
        for resp in self.responsibilities:
            # 简单提取关键词
            for r in self.requirements:
                if r.skill in resp:
                    keywords.add(r.skill)
        return list(keywords)


class JobCreate(BaseModel):
    """创建岗位请求"""
    raw_text: str = Field(..., description="JD原始文本")
    source_url: str = Field("", description="来源链接")


class JobResponse(BaseModel):
    """岗位响应"""
    id: int
    data: JobData
    created_at: datetime
