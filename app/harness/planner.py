"""规划模块 - 任务分解与执行计划

负责将复杂任务分解为可执行的步骤序列。
"""
from typing import List, Dict, Optional
from dataclasses import dataclass, field
from enum import Enum
from loguru import logger


class PlanStatus(Enum):
    """计划状态"""
    PENDING = "pending"      # 待执行
    RUNNING = "running"      # 执行中
    COMPLETED = "completed"  # 已完成
    FAILED = "failed"        # 失败
    SKIPPED = "skipped"      # 跳过


@dataclass
class PlanStep:
    """计划步骤"""
    step_id: int
    action: str              # 执行的动作描述
    tool_name: str           # 使用的工具名
    input_desc: str          # 输入说明
    expected_output: str     # 预期输出
    status: PlanStatus = PlanStatus.PENDING
    actual_output: Optional[str] = None
    error: Optional[str] = None


@dataclass
class ExecutionPlan:
    """执行计划"""
    task_summary: str
    steps: List[PlanStep] = field(default_factory=list)
    current_step: int = 0
    is_completed: bool = False
    
    def get_next_step(self) -> Optional[PlanStep]:
        """获取下一步骤"""
        if self.current_step >= len(self.steps):
            return None
        return self.steps[self.current_step]
    
    def advance(self) -> bool:
        """推进到下一步，返回是否还有步骤"""
        self.current_step += 1
        if self.current_step >= len(self.steps):
            self.is_completed = True
            return False
        return True
    
    def mark_step_completed(self, output: str):
        """标记当前步骤完成"""
        if self.current_step < len(self.steps):
            self.steps[self.current_step].status = PlanStatus.COMPLETED
            self.steps[self.current_step].actual_output = output
    
    def mark_step_failed(self, error: str):
        """标记当前步骤失败"""
        if self.current_step < len(self.steps):
            self.steps[self.current_step].status = PlanStatus.FAILED
            self.steps[self.current_step].error = error


class TaskPlanner:
    """任务规划器"""
    
    def __init__(self, llm_adapter=None):
        self.llm = llm_adapter
        logger.info("TaskPlanner初始化")
    
    def create_plan(self, task: str, available_tools: List[str] = None) -> ExecutionPlan:
        """创建执行计划
        
        如果有LLM，使用LLM生成计划；否则使用规则匹配。
        """
        if self.llm:
            plan = self._create_plan_with_llm(task, available_tools)
        else:
            plan = self._create_plan_with_rules(task)
        self._observe_plan(plan)
        return plan

    @staticmethod
    def _observe_plan(plan: "ExecutionPlan") -> None:
        """L4 决策链埋点（SDD §4.5 P1）：记录 plan span。静默降级。"""
        try:
            from app.observability.context import add_span
            add_span("plan", plan_steps=len(plan.steps),
                     tool_choice=[s.tool_name for s in plan.steps])
        except Exception:
            pass
    
    def _create_plan_with_llm(self, task: str, available_tools: List[str] = None) -> ExecutionPlan:
        """使用LLM创建执行计划"""
        from app.prompts.templates import PromptManager
        
        tools_str = ", ".join(available_tools) if available_tools else "无可用工具"
        
        prompt = PromptManager.get(
            "task_planning",
            user_task=task,
            available_tools=tools_str
        )
        
        try:
            response = self.llm.chat([{"role": "user", "content": prompt}])
            # TODO: 解析LLM返回的JSON，构建ExecutionPlan
            # 骨架阶段先降级到规则匹配
            logger.warning("LLM计划解析尚未实现，降级到规则匹配")
            return self._create_plan_with_rules(task)
        except Exception as e:
            logger.error(f"LLM计划生成失败: {e}")
            return self._create_plan_with_rules(task)
    
    def _create_plan_with_rules(self, task: str) -> ExecutionPlan:
        """使用规则创建执行计划（降级方案）"""
        task_lower = task.lower()
        steps = []
        
        # 简历相关任务
        if "简历" in task_lower and ("解析" in task_lower or "导入" in task_lower):
            steps = [
                PlanStep(1, "解析简历文件", "parse_resume", "简历文件路径", "结构化简历数据"),
            ]
        
        elif "简历" in task_lower and ("优化" in task_lower or "改写" in task_lower):
            steps = [
                PlanStep(1, "解析简历", "parse_resume", "简历文件", "结构化简历数据"),
                PlanStep(2, "解析JD", "parse_jd", "JD文本", "结构化JD数据"),
                PlanStep(3, "优化简历", "optimize_resume", "简历+JD", "优化后简历"),
            ]
        
        # JD/岗位相关任务
        elif "jd" in task_lower or "岗位" in task_lower:
            if "评分" in task_lower or "匹配" in task_lower:
                steps = [
                    PlanStep(1, "解析简历", "parse_resume", "简历文件", "结构化简历数据"),
                    PlanStep(2, "解析JD", "parse_jd", "JD文本", "结构化JD数据"),
                    PlanStep(3, "评分匹配度", "score_job", "简历+JD数据", "评分结果"),
                ]
            else:
                steps = [
                    PlanStep(1, "解析JD", "parse_jd", "JD文本", "结构化JD数据"),
                ]
        
        # 面试相关任务
        elif "面试" in task_lower:
            if "模拟" in task_lower:
                steps = [
                    PlanStep(1, "生成面试题", "generate_questions", "JD+面试类型", "面试题列表"),
                    PlanStep(2, "模拟面试", "mock_interview", "题目+回答", "反馈评价"),
                ]
            else:
                steps = [
                    PlanStep(1, "生成面试题", "generate_questions", "JD+面试类型", "面试题列表"),
                ]
        
        # 默认：简单回复
        else:
            steps = []
        
        plan = ExecutionPlan(
            task_summary=task[:100],
            steps=steps
        )
        
        logger.info(f"创建执行计划: {plan.task_summary}, 步骤数: {len(steps)}")
        return plan
    
    def replan(self, plan: ExecutionPlan, error_info: str) -> ExecutionPlan:
        """重新规划（当执行失败时）"""
        logger.warning(f"触发重新规划，原因: {error_info}")
        # 骨架阶段：简单跳过失败步骤
        if plan.current_step < len(plan.steps):
            plan.steps[plan.current_step].status = PlanStatus.SKIPPED
            plan.advance()
        return plan
