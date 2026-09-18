"""简历优化服务"""
from typing import Optional, Dict, Any, List
from loguru import logger

from app.llm.client import get_llm_client
from app.llm.prompts import PromptTemplates
from app.models.resume import ResumeData
from app.models.job import JobData


class ResumeOptimizerService:
    """简历优化服务"""
    
    def __init__(self):
        self.llm_client = get_llm_client()
    
    def optimize(self, resume_data: ResumeData, job_data: JobData) -> Dict[str, Any]:
        """根据岗位优化简历"""
        logger.info(f"开始优化简历: 目标岗位={job_data.title}")
        
        # 构建原始简历文本
        original_resume = resume_data.to_text()
        
        # 构建目标岗位信息
        target_job = self._build_job_description(job_data)
        
        # 构建prompt
        prompt = PromptTemplates.format_template(
            "OPTIMIZE_RESUME",
            original_resume=original_resume,
            target_job=target_job
        )
        messages = [{"role": "user", "content": prompt}]
        
        # 调用LLM
        try:
            result = self.llm_client.chat_json_sync(messages, temperature=0.5)
            logger.info("简历优化完成")
            return result
        except Exception as e:
            logger.error(f"简历优化失败: {e}")
            return {
                "optimized_resume": original_resume,
                "changes": [],
                "keywords_added": [],
                "tips": ["简历优化服务暂时不可用"]
            }
    
    def _build_job_description(self, job_data: JobData) -> str:
        """构建岗位描述"""
        lines = [
            f"岗位名称: {job_data.title}",
            f"公司: {job_data.company}",
        ]
        
        if job_data.requirements:
            lines.append("\n核心要求:")
            for req in job_data.requirements:
                required_str = "必须" if req.required else "加分"
                lines.append(f"- [{required_str}] {req.skill}")
        
        if job_data.responsibilities:
            lines.append("\n岗位职责:")
            for resp in job_data.responsibilities[:5]:
                lines.append(f"- {resp}")
        
        return "\n".join(lines)
    
    def get_optimization_suggestions(self, resume_data: ResumeData, job_data: JobData) -> List[str]:
        """获取优化建议（不修改简历）"""
        suggestions = []
        
        # 检查技能匹配
        resume_skills = set(s.lower() for s in resume_data.get_all_skills())
        job_skills = job_data.get_all_skills()
        
        missing_skills = []
        for skill in job_skills:
            if skill.lower() not in resume_skills and not any(
                skill.lower() in s.lower() for s in resume_skills
            ):
                missing_skills.append(skill)
        
        if missing_skills:
            suggestions.append(f"建议补充以下技能: {', '.join(missing_skills[:5])}")
        
        # 检查关键词覆盖
        job_keywords = set(k.lower() for k in job_data.get_keywords())
        resume_text = resume_data.to_text().lower()
        
        uncovered = [k for k in job_keywords if k not in resume_text]
        if uncovered:
            suggestions.append(f"简历中缺少以下关键词: {', '.join(list(uncovered)[:5])}")
        
        # 检查工作年限
        if job_data.years_required > resume_data.years_of_experience:
            gap = job_data.years_required - resume_data.years_of_experience
            suggestions.append(f"工作经验差距: 岗位要求{job_data.years_required}年，你目前{resume_data.years_of_experience}年")
        
        return suggestions
    
    def check_keywords_coverage(self, resume_data: ResumeData, job_data: JobData) -> Dict[str, Any]:
        """检查关键词覆盖率"""
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
        
        total = len(job_skills)
        coverage = len(matched) / max(total, 1) * 100
        
        return {
            "total_keywords": total,
            "matched_keywords": matched,
            "missing_keywords": missing,
            "coverage_rate": round(coverage, 2)
        }
