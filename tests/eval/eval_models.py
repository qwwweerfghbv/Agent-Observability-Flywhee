"""评测框架核心数据模型

定义评测用例、评测结果、评测报告的数据结构。
对应文档: 求职Agent评测集模板.md
"""
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum
from dataclasses import dataclass, field


# ===== 枚举定义 =====

class ModuleType(str, Enum):
    """评测模块类型"""
    # v1.0 决策层（业务功能）
    RESUME_PARSE = "resume_parse"
    JD_PARSE = "jd_parse"
    JOB_SCORE = "job_score"
    RESUME_OPTIMIZE = "resume_optimize"
    INTERVIEW = "interview"
    CHAT_ENGINE = "chat_engine"
    E2E = "e2e"
    SECURITY = "security"
    ENV_DEGRADATION = "env_degradation"
    # v2.0 新增维度
    INPUT_LAYER = "input_layer"          # 输入层 — 用户表达覆盖度
    ROUTING_LAYER = "routing_layer"      # 路由层 — 意图到工具的分发
    RETRIEVAL_LAYER = "retrieval_layer"  # 检索层 — 知识与数据召回
    TRAJECTORY_LAYER = "trajectory_layer" # 轨迹层 — 完整执行路径
    STATE_LAYER = "state_layer"          # 状态层 — 系统状态一致性
    BUSINESS_LAYER = "business_layer"    # 业务层 — 任务完成率
    INTERACTION = "interaction"          # 交互性指标
    SECURITY_DEEP = "security_deep"      # 安全性深度测试
    ADVERSARIAL = "adversarial"          # 对抗性压力测试
    SYSTEM_METRIC = "system_metric"      # 系统级指标
    ROBUSTNESS = "robustness"            # 鲁棒性测试
    EXPERIENCE_LAYER = "experience_layer"  # 体验层 — 全链路延迟（首屏/端到端/交互）


class Priority(str, Enum):
    """用例优先级"""
    P0 = "P0"   # 必须通过（质量门禁）
    P1 = "P1"   # 重要
    P2 = "P2"   # 增强


class RiskLevel(str, Enum):
    """风险等级"""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class EvalMethod(str, Enum):
    """评分方式"""
    RULE = "rule"
    LLM_JUDGE = "llm_judge"
    RULE_LLM = "rule+llm_judge"
    HUMAN = "human"


# ===== 评测用例模型 =====

class EvalInput(BaseModel):
    """评测输入"""
    user_message: str = Field("", description="用户原始消息")
    resume_text: str = Field("", description="简历文本")
    jd_text: str = Field("", description="JD文本")
    input_type: str = Field("text", description="输入类型: text/pdf/docx")
    conversation_history: List[Dict[str, str]] = Field(default_factory=list)
    context: Dict[str, Any] = Field(default_factory=dict)
    # 模块特定输入
    jd_parsed: Optional[Dict] = None
    resume_parsed: Optional[Dict] = None
    base_resume: Optional[Dict] = None
    target_jd: Optional[Dict] = None
    interview_type: str = ""
    question_count: int = 0
    current_question: str = ""
    user_answer: str = ""
    dialog_sequence: List[Dict] = Field(default_factory=list)
    scenario: str = ""
    # 安全测试
    jd_attachment: str = ""


class ExpectedResult(BaseModel):
    """期望结果"""
    # 路由层
    intent: str = Field("", description="期望识别的意图")
    tool_chain: List[str] = Field(default_factory=list, description="期望工具调用链")
    # 决策层 - 字段提取
    fields: Dict[str, Any] = Field(default_factory=dict, description="期望提取的字段")
    required_fields: List[str] = Field(default_factory=list)
    optional_fields: List[str] = Field(default_factory=list)
    # 决策层 - 评分
    score: Optional[Dict[str, Any]] = None
    # 决策层 - 优化
    diff_items_min: int = 0
    diff_sections: List[str] = Field(default_factory=list)
    keyword_coverage_min: float = 0
    truthfulness: Optional[Dict[str, Any]] = None
    diff_required_fields: List[str] = Field(default_factory=list)
    min_diff_sections: int = 0
    diff_items: List[Dict] = Field(default_factory=list)
    # 面试
    questions: Optional[Dict[str, Any]] = None
    feedback: Optional[Dict[str, Any]] = None
    # 安全约束
    forbidden: List[str] = Field(default_factory=list, description="禁止出现的内容")
    forbidden_in_output: List[str] = Field(default_factory=list)
    # 响应约束
    response_constraints: Optional[Dict[str, Any]] = None
    # 行为约束
    expected_behavior: str = ""
    expected_warning_contains: str = ""
    # 端到端
    final_state: Optional[Dict[str, Any]] = None
    steps_must_include: List[str] = Field(default_factory=list)
    forbidden_actions: List[str] = Field(default_factory=list)
    # 容错
    tolerance: Optional[Dict[str, Any]] = None
    # 稳定性信号
    stability_signals: Optional[Dict[str, Any]] = None
    # 其他
    behavior: str = ""
    expected_response_contains: List[str] = Field(default_factory=list)
    all_types_generated: bool = False
    types: List[str] = Field(default_factory=list)
    direction_match: Optional[bool] = None
    expected_first_project: str = ""


class EvalCriteria(BaseModel):
    """评分规则"""
    method: str = Field("rule", description="评分方式: rule/llm_judge/rule+llm_judge/human")
    pass_criteria: str = Field("", description="通过条件描述")
    field_accuracy_weight: float = Field(0.6)
    field_completeness_weight: float = Field(0.4)


class EvalCase(BaseModel):
    """评测用例"""
    id: str = Field(..., description="唯一标识")
    module: str = Field(..., description="所属模块")
    sub_type: str = Field("", description="子类型")
    priority: str = Field("P0", description="优先级")
    risk_level: str = Field("medium", description="风险等级")
    tags: List[str] = Field(default_factory=list)
    input: EvalInput = Field(default_factory=EvalInput)
    expected: ExpectedResult = Field(default_factory=ExpectedResult)
    eval: EvalCriteria = Field(default_factory=EvalCriteria)


# ===== 评测结果模型 =====

class SubScore(BaseModel):
    """子项评分"""
    name: str = Field(..., description="评分项名称")
    score: float = Field(0, description="得分 (0-1)")
    weight: float = Field(1.0, description="权重")
    detail: str = Field("", description="评分详情")


class CaseResult(BaseModel):
    """单条用例评测结果"""
    case_id: str = Field(..., description="用例ID")
    module: str = Field(..., description="所属模块")
    priority: str = Field("P0")
    tags: List[str] = Field(default_factory=list)
    
    # 执行状态
    status: str = Field("pending", description="pending/running/passed/failed/error/skipped")
    error_message: str = Field("", description="错误信息")
    
    # 实际输出
    actual: Dict[str, Any] = Field(default_factory=dict, description="实际输出")
    
    # 评分
    sub_scores: List[SubScore] = Field(default_factory=list)
    weighted_score: float = Field(0, description="加权得分")
    passed: bool = Field(False, description="是否通过")
    
    # 红线检查
    red_line_violations: List[str] = Field(default_factory=list)
    
    # 性能
    latency_ms: float = Field(0, description="耗时(毫秒)")
    token_usage: int = Field(0, description="Token消耗")
    
    # 失败分析
    failure_reason: str = Field("", description="失败原因")
    failure_severity: str = Field("", description="失败严重度: critical/high/medium/low")
    
    # 时间戳
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())


# ===== 质量门禁 =====

class QualityGates(BaseModel):
    """质量门禁配置"""
    overall_pass_rate: float = Field(0.85, description="总通过率阈值")
    critical: Dict[str, Any] = Field(default_factory=lambda: {
        "truthfulness_violation": 0,
        "sensitive_data_leak": 0,
        "unauthorized_action": 0,
        "hard_filter_accuracy": 0.98
    })
    performance: Dict[str, Any] = Field(default_factory=lambda: {
        "p95_simple_latency_s": 5,
        "p95_complex_latency_s": 15,
        "error_rate": 0.03
    })


# ===== 评测报告 =====

class ModuleReport(BaseModel):
    """模块评测报告"""
    module: str
    total: int = 0
    passed: int = 0
    failed: int = 0
    error: int = 0
    skipped: int = 0
    pass_rate: float = 0.0
    avg_latency_ms: float = 0.0
    red_line_violations: int = 0


class EvalReport(BaseModel):
    """评测报告"""
    run_id: str = Field(..., description="运行ID")
    dataset_version: str = Field("1.0.0")
    agent_version: str = Field("0.3.0")
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())
    
    # 总览
    total_cases: int = 0
    passed: int = 0
    failed: int = 0
    error: int = 0
    skipped: int = 0
    pass_rate: float = 0.0
    
    # 质量门禁
    gate_passed: bool = False
    gate_details: Dict[str, Any] = Field(default_factory=dict)
    
    # 分模块
    by_module: Dict[str, ModuleReport] = Field(default_factory=dict)
    
    # 红线
    truthfulness_violations: int = 0
    sensitive_data_leaks: int = 0
    unauthorized_actions: int = 0
    
    # 性能
    p50_latency_ms: float = 0
    p95_latency_ms: float = 0
    total_tokens: int = Field(0, description="本次运行LLM累计Token消耗")
    avg_token_per_task: float = 0
    total_cost_yuan: float = 0
    
    # 失败用例
    failed_cases: List[Dict[str, Any]] = Field(default_factory=list)

    # 意图混淆矩阵（Macro-F1 防头部高频意图掩盖长尾意图效果差）
    intent_pairs: List[Dict[str, str]] = Field(default_factory=list)
    intent_confusion: Dict[str, Any] = Field(default_factory=dict)
    intent_macro_f1: float = 0.0
    
    # 详细结果
    case_results: List[CaseResult] = Field(default_factory=list)


# ===== 用户画像（评测集共享上下文）=====

class UserProfile(BaseModel):
    """用户基础画像"""
    name: str = "张三"
    phone: str = "13800138000"
    email: str = "zhangsan@example.com"
    target_city: str = "杭州"
    expected_salary_min: int = 27
    target_positions: List[str] = Field(default_factory=lambda: ["AI测试开发", "AI Agent评测"])
    excluded_keywords: List[str] = Field(default_factory=lambda: ["外包", "人力外派", "驻场", "项目外包"])
    years_of_experience: int = 5
    core_skills: List[str] = Field(default_factory=lambda: [
        "Python", "pytest", "Selenium", "Appium", "CI/CD", "Jenkins", "GitLab CI", "Docker", "FastAPI"
    ])
