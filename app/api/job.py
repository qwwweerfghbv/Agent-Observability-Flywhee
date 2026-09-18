"""岗位API路由"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Optional
from loguru import logger

from app.db.database import get_db
from app.db.repositories import JobRepository, ResumeRepository, ScoreRepository
from app.services.job_parser import JobParserService
from app.services.job_scorer import JobScorerService
from app.models.job import JobCreate, JobResponse, JobData
from app.models.resume import ResumeData
from app.models.score import ScoreRequest, ScoreResponse, ScoreResult

router = APIRouter(prefix="/api/job", tags=["岗位管理"])


@router.post("/parse", response_model=JobResponse)
async def parse_job(
    request: JobCreate,
    db: Session = Depends(get_db)
):
    """解析JD文本"""
    logger.info("收到JD解析请求")
    
    # 解析JD
    parser = JobParserService()
    job_data = parser.parse(request.raw_text)
    
    # 保存到数据库
    repo = JobRepository(db)
    record = repo.create(job_data, request.raw_text)
    
    return JobResponse(
        id=record.id,
        data=job_data,
        created_at=record.created_at
    )


@router.get("/{job_id}", response_model=JobResponse)
async def get_job(
    job_id: int,
    db: Session = Depends(get_db)
):
    """获取岗位详情"""
    repo = JobRepository(db)
    record = repo.get_by_id(job_id)
    
    if not record:
        raise HTTPException(status_code=404, detail="岗位不存在")
    
    return JobResponse(
        id=record.id,
        data=JobData(**record.data_json),
        created_at=record.created_at
    )


@router.get("/")
async def list_jobs(
    limit: int = 10,
    db: Session = Depends(get_db)
):
    """获取岗位列表"""
    repo = JobRepository(db)
    records = repo.get_all(limit=limit)
    
    return {
        "total": len(records),
        "jobs": [
            {
                "id": r.id,
                "title": r.title,
                "company": r.company,
                "location": r.location,
                "salary": f"{r.salary_min}-{r.salary_max}万",
                "created_at": r.created_at.isoformat() if r.created_at else None
            }
            for r in records
        ]
    }


@router.delete("/{job_id}")
async def delete_job(
    job_id: int,
    db: Session = Depends(get_db)
):
    """删除岗位"""
    repo = JobRepository(db)
    success = repo.delete(job_id)
    
    if not success:
        raise HTTPException(status_code=404, detail="岗位不存在")
    
    return {"message": "删除成功"}


@router.post("/score", response_model=ScoreResponse)
async def score_job(
    request: ScoreRequest,
    db: Session = Depends(get_db)
):
    """评估简历与岗位的匹配度"""
    logger.info(f"收到评分请求: resume_id={request.resume_id}, job_id={request.job_id}")
    
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
    
    # 评分
    scorer = JobScorerService()
    resume_data = ResumeData(**resume_record.data_json)
    job_data = JobData(**job_record.data_json)
    
    score_result = scorer.score(resume_data, job_data)
    score_result.resume_id = request.resume_id
    score_result.job_id = request.job_id
    
    # 保存评分结果
    score_repo = ScoreRepository(db)
    score_record = score_repo.create(score_result)
    
    return ScoreResponse(
        result=score_result,
        resume_summary=f"{resume_data.name} - {resume_data.years_of_experience}年经验",
        job_summary=f"{job_data.title} - {job_data.company}"
    )


@router.get("/scores/{score_id}")
async def get_score(
    score_id: int,
    db: Session = Depends(get_db)
):
    """获取评分详情"""
    repo = ScoreRepository(db)
    result = repo.get_score_result(score_id)
    
    if not result:
        raise HTTPException(status_code=404, detail="评分记录不存在")
    
    return {"result": result}


@router.get("/scores/by-resume/{resume_id}")
async def get_scores_by_resume(
    resume_id: int,
    limit: int = 10,
    db: Session = Depends(get_db)
):
    """获取简历的所有评分"""
    repo = ScoreRepository(db)
    records = repo.get_by_resume(resume_id, limit=limit)
    
    return {
        "resume_id": resume_id,
        "total": len(records),
        "scores": [
            {
                "id": r.id,
                "job_id": r.job_id,
                "total_score": r.total_score,
                "score_level": r.score_level,
                "created_at": r.created_at.isoformat() if r.created_at else None
            }
            for r in records
        ]
    }
