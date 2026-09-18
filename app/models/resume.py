"""简历数据模型"""
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime


class Education(BaseModel):
    """教育经历"""
    school: str = Field(..., description="学校名称")
    degree: str = Field(..., description="学历：本科/硕士/博士")
    major: str = Field(..., description="专业")
    start_date: str = Field("", description="开始时间")
    end_date: str = Field("", description="结束时间")
    gpa: Optional[str] = Field(None, description="GPA")


class WorkExperience(BaseModel):
    """工作经历"""
    company: str = Field(..., description="公司名称")
    position: str = Field(..., description="职位")
    start_date: str = Field("", description="开始时间")
    end_date: str = Field("", description="结束时间，在职则留空")
    description: str = Field("", description="工作内容描述")
    achievements: List[str] = Field(default_factory=list, description="主要成就")


class Project(BaseModel):
    """项目经历"""
    name: str = Field(..., description="项目名称")
    role: str = Field("", description="担任角色")
    description: str = Field("", description="项目描述")
    technologies: List[str] = Field(default_factory=list, description="使用的技术")
    achievements: List[str] = Field(default_factory=list, description="项目成果")


class Skill(BaseModel):
    """技能"""
    name: str = Field(..., description="技能名称")
    level: str = Field("熟悉", description="熟练度：了解/熟悉/掌握/精通")
    category: str = Field("", description="技能类别：编程语言/框架/工具/其他")


class ResumeData(BaseModel):
    """简历结构化数据"""
    # 基本信息
    name: str = Field("", description="姓名")
    phone: str = Field("", description="电话")
    email: str = Field("", description="邮箱")
    location: str = Field("", description="所在城市")
    years_of_experience: float = Field(0, description="工作年限")
    
    # 教育经历
    educations: List[Education] = Field(default_factory=list)
    
    # 工作经历
    work_experiences: List[WorkExperience] = Field(default_factory=list)
    
    # 项目经历
    projects: List[Project] = Field(default_factory=list)
    
    # 技能
    skills: List[Skill] = Field(default_factory=list)
    
    # 自我评价
    summary: str = Field("", description="自我评价/个人简介")
    
    # 元数据
    raw_text: str = Field("", description="原始文本内容")
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    
    def get_all_skills(self) -> List[str]:
        """获取所有技能名称"""
        return [s.name for s in self.skills]
    
    def get_all_keywords(self) -> List[str]:
        """获取所有关键词（技能+项目技术）"""
        keywords = set(self.get_all_skills())
        for proj in self.projects:
            keywords.update(proj.technologies)
        for work in self.work_experiences:
            # 简单提取技术关键词
            for skill in self.skills:
                if skill.name in work.description:
                    keywords.add(skill.name)
        return list(keywords)
    
    def to_text(self) -> str:
        """转换为纯文本格式"""
        lines = []
        lines.append(f"# {self.name}")
        if self.phone or self.email:
            lines.append(f"联系方式: {self.phone} | {self.email}")
        if self.location:
            lines.append(f"所在地: {self.location}")
        lines.append("")
        
        if self.summary:
            lines.append("## 个人简介")
            lines.append(self.summary)
            lines.append("")
        
        if self.work_experiences:
            lines.append("## 工作经历")
            for work in self.work_experiences:
                lines.append(f"### {work.company} - {work.position}")
                if work.start_date:
                    lines.append(f"{work.start_date} - {work.end_date or '至今'}")
                if work.description:
                    lines.append(work.description)
                for ach in work.achievements:
                    lines.append(f"- {ach}")
                lines.append("")
        
        if self.projects:
            lines.append("## 项目经历")
            for proj in self.projects:
                lines.append(f"### {proj.name}")
                if proj.role:
                    lines.append(f"角色: {proj.role}")
                if proj.description:
                    lines.append(proj.description)
                if proj.technologies:
                    lines.append(f"技术栈: {', '.join(proj.technologies)}")
                for ach in proj.achievements:
                    lines.append(f"- {ach}")
                lines.append("")
        
        if self.skills:
            lines.append("## 技能")
            for skill in self.skills:
                lines.append(f"- {skill.name} ({skill.level})")
            lines.append("")
        
        if self.educations:
            lines.append("## 教育背景")
            for edu in self.educations:
                lines.append(f"- {edu.school} | {edu.degree} | {edu.major}")
            lines.append("")
        
        return "\n".join(lines)


class ResumeCreate(BaseModel):
    """创建简历请求"""
    raw_text: str = Field(..., description="简历原始文本")
    file_type: str = Field("text", description="文件类型: text/pdf/docx")


class ResumeResponse(BaseModel):
    """简历响应"""
    id: int
    data: ResumeData
    created_at: datetime
