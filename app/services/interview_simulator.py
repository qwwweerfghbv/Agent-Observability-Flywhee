"""面试模拟服务"""
from typing import List, Dict, Any, Optional
from loguru import logger

from app.llm.client import get_llm_client
from app.llm.prompts import PromptTemplates
from app.models.job import JobData


class InterviewSimulatorService:
    """面试模拟服务"""
    
    def __init__(self):
        self.llm_client = get_llm_client()
    
    def generate_questions(self, job_data: JobData) -> Dict[str, Any]:
        """根据岗位生成面试题目"""
        logger.info(f"生成面试题: 岗位={job_data.title}")
        
        # 构建岗位信息
        job_info = self._build_job_info(job_data)
        
        # 构建prompt
        prompt = PromptTemplates.format_template(
            "GENERATE_QUESTIONS",
            job_info=job_info
        )
        messages = [{"role": "user", "content": prompt}]
        
        # 调用LLM
        try:
            result = self.llm_client.chat_json_sync(messages, temperature=0.7)
            logger.info("面试题生成完成")
            return result
        except Exception as e:
            logger.error(f"面试题生成失败: {e}")
            return self._default_questions(job_data)
    
    def _build_job_info(self, job_data: JobData) -> str:
        """构建岗位信息"""
        lines = [
            f"岗位名称: {job_data.title}",
            f"公司: {job_data.company}",
            f"要求工作年限: {job_data.years_required}年",
        ]
        
        if job_data.requirements:
            lines.append("\n核心技能要求:")
            for req in job_data.requirements:
                lines.append(f"- {req.skill}")
        
        if job_data.responsibilities:
            lines.append("\n岗位职责:")
            for resp in job_data.responsibilities[:5]:
                lines.append(f"- {resp}")
        
        return "\n".join(lines)
    
    def _default_questions(self, job_data: JobData) -> Dict[str, Any]:
        """默认面试题（LLM失败时使用）

        降级韧性：始终覆盖 technical/behavioral/hr 三类，且技术题在岗位未给出
        显式技能时从岗位名称派生，避免降级返回空题或缺失 HR 类（IV-003/IV-007）。
        """
        technical = []
        for skill in job_data.get_all_skills()[:5]:
            technical.append({
                "question": f"请介绍一下你对{skill}的理解和使用经验",
                "skill": skill,
                "difficulty": "中等",
                "key_points": ["基本原理", "实际应用场景", "遇到的问题及解决方案"],
                "reference_answer": f"候选人应该展示对{skill}的理解和实际使用经验"
            })
        if not technical:
            title = job_data.title or "目标岗位"
            for q in (
                f"请结合「{title}」岗位，介绍一个你最有代表性的项目经验",
                f"「{title}」岗位需要哪些核心技能？你是如何掌握并在工作中应用它们的？",
                f"你如何保证「{title}」相关工作的质量与效率？请举例说明",
            ):
                technical.append({
                    "question": q,
                    "skill": title,
                    "difficulty": "中等",
                    "key_points": ["基本原理", "实际应用场景", "遇到的问题及解决方案"],
                    "reference_answer": f"候选人应展示与「{title}」相关的实战经验与思考"
                })
        
        behavioral = [
            {
                "question": "请描述一个你解决过的最复杂的技术问题",
                "competency": "问题解决能力",
                "star_guide": "Situation: 描述背景, Task: 你的任务, Action: 采取的行动, Result: 最终结果"
            },
            {
                "question": "请举例说明你如何在团队中发挥作用",
                "competency": "团队协作",
                "star_guide": "Situation: 项目背景, Task: 你的角色, Action: 具体贡献, Result: 团队成果"
            }
        ]
        
        hr = [
            {
                "question": "请做一个简单的自我介绍",
                "topic": "自我介绍",
                "reference_answer": "简述个人背景、核心技能与求职动机"
            },
            {
                "question": "你从上一家公司离职的原因是什么？",
                "topic": "离职原因",
                "reference_answer": "客观说明，聚焦职业发展与个人成长"
            },
            {
                "question": "未来3年你的职业规划是怎样的？",
                "topic": "职业规划",
                "reference_answer": "结合目标岗位方向说明清晰的成长路径"
            }
        ]
        
        return {
            "technical_questions": technical,
            "behavioral_questions": behavioral,
            "hr_questions": hr
        }
    
    def evaluate_answer(self, question: str, answer: str) -> Dict[str, Any]:
        """评估候选人的回答"""
        logger.info("评估回答...")
        
        # 构建prompt
        prompt = PromptTemplates.format_template(
            "EVALUATE_ANSWER",
            question=question,
            answer=answer
        )
        messages = [{"role": "user", "content": prompt}]
        
        # 调用LLM
        try:
            result = self.llm_client.chat_json_sync(messages, temperature=0.5)
            logger.info("回答评估完成")
            return result
        except Exception as e:
            logger.error(f"回答评估失败: {e}")
            # 降级韧性：改进建议引用题目主题，避免空泛到无法指导（IV-006）
            q_hint = (question or "").strip()[:40]
            return {
                "score": 60,
                "strengths": ["回答完整"],
                "weaknesses": ["可以更具体"],
                "improvements": [
                    f"请紧扣「{q_hint}」补充具体指标、数据与实际案例",
                    "使用STAR法则组织回答，突出你的具体贡献与量化成果"
                ],
                "reference_answer": f"建议结合具体项目经验，围绕「{q_hint}」展开作答"
            }
    
    def start_mock_interview(self, job_data: JobData) -> Dict[str, Any]:
        """开始模拟面试会话"""
        questions = self.generate_questions(job_data)
        
        return {
            "job_title": job_data.title,
            "total_questions": len(questions.get("technical_questions", [])) + 
                             len(questions.get("behavioral_questions", [])),
            "questions": questions,
            "status": "ready",
            "message": f"已为{job_data.title}岗位准备面试题，共{len(questions.get('technical_questions', []))}道技术题和{len(questions.get('behavioral_questions', []))}道行为题"
        }
