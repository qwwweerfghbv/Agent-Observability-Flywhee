"""面试和简历优化API路由"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Optional
from pydantic import BaseModel, Field
from loguru import logger

from app.db.database import get_db
from app.db.repositories import JobRepository, ResumeRepository
from app.services.interview_simulator import InterviewSimulatorService
from app.services.resume_optimizer import ResumeOptimizerService
from app.models.job import JobData
from app.models.resume import ResumeData

router = APIRouter(prefix="/api", tags=["面试与优化"])


# ==================== 简历优化 ====================

class OptimizeRequest(BaseModel):
    """简历优化请求"""
    resume_id: int = Field(..., description="简历ID")
    job_id: int = Field(..., description="目标岗位ID")


@router.post("/optimize")
async def optimize_resume(
    request: OptimizeRequest,
    db: Session = Depends(get_db)
):
    """根据岗位优化简历"""
    logger.info(f"收到简历优化请求: resume_id={request.resume_id}, job_id={request.job_id}")
    
    # 获取简历
    resume_repo = ResumeRepository(db)
    resume_record = resume_repo.get_by_id(request.resume_id)
    if not resume_record:
        raise HTTPException(status_code=404, detail="简历不存在")
    
    # 获取岗位
    job_repo = JobRepository(db)
    job_record = job_repo.get_by_id(request.job_id)
    if not job_record:
        raise HTTPException(status_code=404, detail="岗位不存在")
    
    # 优化
    optimizer = ResumeOptimizerService()
    resume_data = ResumeData(**resume_record.data_json)
    job_data = JobData(**job_record.data_json)
    
    result = optimizer.optimize(resume_data, job_data)
    
    return {
        "resume_id": request.resume_id,
        "job_id": request.job_id,
        "result": result
    }


@router.post("/optimize/suggestions")
async def get_optimization_suggestions(
    request: OptimizeRequest,
    db: Session = Depends(get_db)
):
    """获取简历优化建议（不修改简历）"""
    # 获取简历
    resume_repo = ResumeRepository(db)
    resume_record = resume_repo.get_by_id(request.resume_id)
    if not resume_record:
        raise HTTPException(status_code=404, detail="简历不存在")
    
    # 获取岗位
    job_repo = JobRepository(db)
    job_record = job_repo.get_by_id(request.job_id)
    if not job_record:
        raise HTTPException(status_code=404, detail="岗位不存在")
    
    optimizer = ResumeOptimizerService()
    resume_data = ResumeData(**resume_record.data_json)
    job_data = JobData(**job_record.data_json)
    
    suggestions = optimizer.get_optimization_suggestions(resume_data, job_data)
    coverage = optimizer.check_keywords_coverage(resume_data, job_data)
    
    return {
        "suggestions": suggestions,
        "keywords_coverage": coverage
    }


# ==================== 面试模拟 ====================

class EvaluateRequest(BaseModel):
    """面试回答评估请求"""
    question: str = Field(..., description="面试题目")
    answer: str = Field(..., description="候选人回答")


@router.post("/interview/generate/{job_id}")
async def generate_interview_questions(
    job_id: int,
    db: Session = Depends(get_db)
):
    """根据岗位生成面试题目"""
    logger.info(f"生成面试题: job_id={job_id}")
    
    # 获取岗位
    job_repo = JobRepository(db)
    job_record = job_repo.get_by_id(job_id)
    if not job_record:
        raise HTTPException(status_code=404, detail="岗位不存在")
    
    job_data = JobData(**job_record.data_json)
    
    # 生成面试题
    simulator = InterviewSimulatorService()
    result = simulator.start_mock_interview(job_data)
    
    return result


@router.post("/interview/evaluate")
async def evaluate_answer(
    request: EvaluateRequest
):
    """评估面试回答"""
    logger.info("评估面试回答")
    
    simulator = InterviewSimulatorService()
    result = simulator.evaluate_answer(request.question, request.answer)
    
    return {
        "question": request.question,
        "evaluation": result
    }
