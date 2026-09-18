"""岗位评分服务"""
from typing import Optional
from loguru import logger

from app.llm.client import get_llm_client
from app.llm.prompts import PromptTemplates
from app.models.resume import ResumeData
from app.models.job import JobData
from app.models.score import ScoreResult, ScoreDetail, SkillMatch


class JobScorerService:
    """岗位评分服务"""
    
    def __init__(self):
        self.llm_client = get_llm_client()
    
    def score(self, resume_data: ResumeData, job_data: JobData) -> ScoreResult:
        """评估简历与岗位的匹配度"""
        logger.info(f"开始评分: 简历={resume_data.name}, 岗位={job_data.title}")
        
        # 构建简历摘要
        resume_summary = self._build_resume_summary(resume_data)
        
        # 构建岗位摘要
        job_summary = self._build_job_summary(job_data)
        
        # 构建稳定性评估（简化版）
        stability_assessment = "暂无详细稳定性评估"
        if job_data.stability_signals:
            signals = job_data.stability_signals
            stability_assessment = f"融资阶段: {signals.get('funding_stage', '未知')}, " \
                                  f"公司规模: {signals.get('company_size', '未知')}, " \
                                  f"AI风险: {signals.get('ai_risk_level', '未知')}"
        
        # 构建prompt
        prompt = PromptTemplates.format_template(
            "SCORE_JOB",
            resume_summary=resume_summary,
            job_summary=job_summary,
            stability_assessment=stability_assessment
        )
        messages = [{"role": "user", "content": prompt}]
        
        # 调用LLM
        try:
            result = self.llm_client.chat_json_sync(messages, temperature=0.3)
            logger.info(f"LLM评分完成")
        except Exception as e:
            logger.error(f"LLM评分失败: {e}")
            # 返回默认评分
            return self._default_score_result(resume_data, job_data)
        
        # 构建评分结果
        return self._build_score_result(result, resume_data, job_data)
    
    def _build_resume_summary(self, resume_data: ResumeData) -> str:
        """构建简历摘要"""
        lines = [
            f"姓名: {resume_data.name}",
            f"工作年限: {resume_data.years_of_experience}年",
            f"所在城市: {resume_data.location}",
            f"技能: {', '.join(resume_data.get_all_skills())}",
        ]
        
        if resume_data.work_experiences:
            lines.append("\n工作经历:")
            for work in resume_data.work_experiences[:3]:
                lines.append(f"- {work.company} {work.position}")
        
        if resume_data.projects:
            lines.append("\n项目经历:")
            for proj in resume_data.projects[:3]:
                lines.append(f"- {proj.name}: {', '.join(proj.technologies)}")
        
        return "\n".join(lines)
    
    def _build_job_summary(self, job_data: JobData) -> str:
        """构建岗位摘要"""
        lines = [
            f"岗位名称: {job_data.title}",
            f"公司: {job_data.company}",
            f"地点: {job_data.location}",
            f"薪资: {job_data.salary_min}-{job_data.salary_max}万/年",
            f"要求年限: {job_data.years_required}年",
            f"学历要求: {job_data.education_required}",
        ]
        
        if job_data.requirements:
            lines.append("\n技能要求:")
            for req in job_data.requirements:
                required_str = "必须" if req.required else "加分"
                lines.append(f"- [{required_str}] {req.skill}")
        
        if job_data.responsibilities:
            lines.append("\n岗位职责:")
            for resp in job_data.responsibilities[:5]:
                lines.append(f"- {resp}")
        
        return "\n".join(lines)
    
    def _build_score_result(self, result: dict, resume_data: ResumeData, job_data: JobData) -> ScoreResult:
        """构建评分结果"""
        # 解析各维度得分
        detail = ScoreDetail(
            skill_score=float(result.get("skill_score", 0)),
            experience_score=float(result.get("experience_score", 0)),
            salary_score=float(result.get("salary_score", 0)),
            stability_score=float(result.get("stability_score", 0)),
            growth_score=float(result.get("growth_score", 0)),
            matched_skills=result.get("matched_skills", []),
            missing_skills=result.get("missing_skills", [])
        )
        
        # 构建技能匹配详情
        skill_matches = []
        resume_skills = set(s.lower() for s in resume_data.get_all_skills())
        job_skills = job_data.get_all_skills()
        
        for skill in job_skills:
            matched = skill.lower() in resume_skills or any(
                skill.lower() in s.lower() for s in resume_skills
            )
            skill_matches.append(SkillMatch(
                skill=skill,
                matched=matched,
                score=100 if matched else 0
            ))
        detail.skill_matches = skill_matches
        
        # 构建评分结果
        score_result = ScoreResult(
            resume_id=0,  # 由调用方设置
            job_id=0,
            detail=detail,
            strengths=result.get("strengths", []),
            weaknesses=result.get("weaknesses", []),
            suggestions=result.get("suggestions", []),
            ai_advice=result.get("ai_advice", "")
        )
        
        # 计算总分
        score_result.calculate_total()
        
        return score_result
    
    def _default_score_result(self, resume_data: ResumeData, job_data: JobData) -> ScoreResult:
        """默认评分结果（LLM失败时使用）"""
        # 简单计算技能匹配度
        resume_skills = set(s.lower() for s in resume_data.get_all_skills())
        job_skills = job_data.get_all_skills()
        
        matched = []
        missing = []
        for skill in job_skills:
            if skill.lower() in resume_skills or any(
                skill.lower() in s.lower() for s in resume_skills
            ):
                matched.append(skill)
            else:
                missing.append(skill)
        
        skill_score = len(matched) / max(len(job_skills), 1) * 100
        
        detail = ScoreDetail(
            skill_score=skill_score,
            experience_score=50,
            salary_score=50,
            stability_score=50,
            growth_score=50,
            matched_skills=matched,
            missing_skills=missing
        )
        
        score_result = ScoreResult(
            resume_id=0,
            job_id=0,
            detail=detail,
            ai_advice="评分服务暂时不可用，仅计算了技能匹配度"
        )
        score_result.calculate_total()
        
        return score_result
