"""Agent执行循环模块 - 带保护的完整循环

集成: LLM + 工具管道 + 轨迹记录 + 状态管理 + 规划 + 反思 + 记忆
"""
from typing import Optional, List, Dict
from dataclasses import dataclass, field
from datetime import datetime
import time
import uuid
from loguru import logger

from .llm_adapter import BaseLLMAdapter, LLMResponse
from .tool_pipeline import ToolPipeline
from .trajectory import TrajectoryRecorder
from .state_manager import StateManager
from .planner import TaskPlanner, ExecutionPlan
from .reflection import Reflection
from app.memory.short_term import ShortTermMemory
from app.memory.long_term import LongTermMemory
from app.prompts.templates import PromptManager


@dataclass
class LoopConfig:
    """循环保护配置"""
    max_turns: int = 20              # 最大轮次
    timeout_seconds: int = 300       # 总超时时间（5分钟）
    single_turn_timeout: int = 30    # 单轮超时（30秒）
    max_retries: int = 3             # 单次失败重试次数
    retry_delay: float = 1.0         # 重试间隔


@dataclass
class LoopState:
    """循环状态"""
    turn: int = 0
    start_time: float = 0
    is_completed: bool = False
    error: Optional[str] = None
    final_output: Optional[str] = None


class AgentLoop:
    """带保护的Agent执行循环（Harness核心）
    
    集成所有最佳实践组件:
    - LLM适配器（可插拔）
    - 工具管道（带拦截）
    - 轨迹记录（可审计）
    - 状态管理（可恢复）
    - 任务规划（任务分解）
    - 反思机制（自我纠错）
    - 短期记忆（上下文窗口）
    - 长期记忆（跨会话）
    """
    
    def __init__(
        self,
        llm_adapter: BaseLLMAdapter,
        tool_pipeline: ToolPipeline,
        trajectory: TrajectoryRecorder,
        state_manager: StateManager,
        planner: TaskPlanner = None,
        reflection: Reflection = None,
        long_term_memory: LongTermMemory = None,
        config: LoopConfig = None
    ):
        self.llm = llm_adapter
        self.tools = tool_pipeline
        self.trajectory = trajectory
        self.state = state_manager
        self.planner = planner
        self.reflection = reflection
        self.long_term_memory = long_term_memory
        self.config = config or LoopConfig()
        
        # 会话级短期记忆（按session_id管理）
        self._short_memories: Dict[str, ShortTermMemory] = {}
        
        logger.info(
            f"AgentLoop初始化 | 模型: {llm_adapter.get_model_name()} | "
            f"最大轮次: {self.config.max_turns} | "
            f"规划: {'有' if planner else '无'} | "
            f"反思: {'有' if reflection else '无'} | "
            f"长期记忆: {'有' if long_term_memory else '无'}"
        )
    
    def _get_short_memory(self, session_id: str) -> ShortTermMemory:
        """获取或创建会话的短期记忆"""
        if session_id not in self._short_memories:
            stm = ShortTermMemory()
            stm.set_system_prompt(PromptManager.get_system_prompt())
            # 注入长期记忆上下文
            if self.long_term_memory:
                context = self.long_term_memory.get_context_for_llm()
                if context:
                    stm.add_message("system", f"[用户背景信息]\n{context}")
            self._short_memories[session_id] = stm
        return self._short_memories[session_id]
    
    def run(self, task: str, session_id: str = None) -> str:
        """执行任务，返回最终结果"""
        # 生成或使用指定session_id
        if session_id is None:
            session_id = str(uuid.uuid4())
        
        logger.info(f"开始执行任务，session: {session_id}, task: {task[:100]}...")
        
        # 初始化循环状态
        loop_state = LoopState(start_time=time.time())
        
        # 恢复或初始化会话状态
        context = self.state.load_or_init(session_id, task)
        
        # 获取短期记忆
        stm = self._get_short_memory(session_id)
        
        # 记录任务开始事件
        self.trajectory.record_event(session_id, {
            "type": "task_start",
            "task": task,
            "session_id": session_id,
            "timestamp": datetime.now().isoformat()
        })
        
        # 添加用户消息到短期记忆
        stm.add_message("user", task)
        
        # 规划阶段（如果有规划模块）
        plan = None
        if self.planner:
            available_tools = self.tools.registry.list_tools()
            plan = self.planner.create_plan(task, available_tools)
            self.trajectory.record_event(session_id, {
                "type": "plan_created",
                "task_summary": plan.task_summary,
                "steps_count": len(plan.steps),
                "timestamp": datetime.now().isoformat()
            })
            logger.info(f"创建执行计划: {len(plan.steps)} 步")
        
        # 添加用户消息到持久状态
        self.state.add_message(session_id, "user", task)
        
        retry_count = 0
        
        try:
            while not loop_state.is_completed:
                # 检查保护条件
                if self._check_protections(loop_state):
                    break
                
                loop_state.turn += 1
                logger.debug(f"轮次 {loop_state.turn}/{self.config.max_turns}")
                
                # 从短期记忆获取上下文
                messages = stm.get_messages()
                
                # 调用LLM
                try:
                    response = self.llm.chat(messages)
                    
                    # 记录模型输出到轨迹
                    self.trajectory.record_event(session_id, {
                        "type": "model_output",
                        "turn": loop_state.turn,
                        "content": response.content,
                        "tool_calls": response.tool_calls,
                        "timestamp": datetime.now().isoformat()
                    })
                    
                    # 解析是否有工具调用
                    if response.has_tool_calls():
                        # 通过工具管道执行
                        for tool_call in response.tool_calls:
                            tool_name = tool_call.get("name")
                            arguments = tool_call.get("arguments", {})
                            
                            result = self.tools.execute(
                                tool_name,
                                arguments,
                                session_id=session_id
                            )
                            
                            # 记录工具执行到轨迹
                            self.trajectory.record_event(session_id, {
                                "type": "tool_execution",
                                "tool_name": tool_name,
                                "arguments": arguments,
                                "result": result,
                                "timestamp": datetime.now().isoformat()
                            })
                            
                            # 将工具结果添加到上下文
                            result_str = str(result.get("data", result.get("error", "执行失败")))
                            stm.add_message("tool", f"工具 {tool_name} 执行结果: {result_str}")
                            self.state.add_message(session_id, "tool", f"工具 {tool_name} 执行结果: {result_str}")
                        
                        # 更新规划步骤（如果有）
                        if plan and not plan.is_completed:
                            plan.mark_step_completed(result_str)
                            plan.advance()
                    else:
                        # 没有工具调用 = 任务可能完成
                        loop_state.is_completed = True
                        loop_state.final_output = response.content
                        
                        # 添加到短期记忆
                        stm.add_message("assistant", response.content)
                        self.state.add_message(session_id, "assistant", response.content)
                        
                        # 反思阶段（如果有反思模块）
                        if self.reflection:
                            reflection_result = self.reflection.evaluate(
                                task=task,
                                output=response.content,
                                trajectory_summary=""
                            )
                            
                            self.trajectory.record_event(session_id, {
                                "type": "reflection",
                                "quality_score": reflection_result.quality_score,
                                "has_issues": reflection_result.has_issues,
                                "issues": reflection_result.issues,
                                "timestamp": datetime.now().isoformat()
                            })
                            
                            # 如果质量不达标且可重试，继续循环
                            if self.reflection.should_retry(reflection_result, retry_count):
                                loop_state.is_completed = False
                                retry_count += 1
                                correction_prompt = self.reflection.generate_correction_prompt(
                                    task, response.content, reflection_result.issues
                                )
                                stm.add_message("system", correction_prompt)
                                logger.info(f"反思触发重试 ({retry_count}): score={reflection_result.quality_score}")
                        
                        self.trajectory.record_event(session_id, {
                            "type": "task_completed",
                            "final_output": response.content,
                            "total_turns": loop_state.turn,
                            "retry_count": retry_count,
                            "timestamp": datetime.now().isoformat()
                        })
                        
                        # 记录到长期记忆
                        if self.long_term_memory:
                            self.long_term_memory.add_operation(
                                op_type="chat",
                                summary=task[:100],
                                result=response.content[:200] if response.content else ""
                            )
                
                except Exception as e:
                    logger.error(f"LLM调用失败: {str(e)}")
                    self.trajectory.record_event(session_id, {
                        "type": "error",
                        "error": str(e),
                        "turn": loop_state.turn,
                        "timestamp": datetime.now().isoformat()
                    })
                    
                    # 重试或终止
                    if loop_state.turn >= self.config.max_retries:
                        loop_state.error = f"LLM调用失败，已重试{self.config.max_retries}次"
                        break
                    time.sleep(self.config.retry_delay)
            
            # 持久化最终状态
            self.state.save(session_id)
            
            # 清理短期记忆
            if session_id in self._short_memories:
                del self._short_memories[session_id]
            
            # 返回结果
            if loop_state.final_output:
                logger.info(f"任务完成，session: {session_id}, 轮次: {loop_state.turn}")
                return loop_state.final_output
            else:
                fallback = self._get_fallback_response(loop_state)
                logger.warning(f"任务未完成，返回降级响应: {fallback}")
                return fallback
                
        except Exception as e:
            logger.error(f"AgentLoop执行异常: {str(e)}")
            self.trajectory.record_event(session_id, {
                "type": "error",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            })
            return f"执行异常: {str(e)}"
    
    def _check_protections(self, state: LoopState) -> bool:
        """检查是否需要终止"""
        # 轮次上限
        if state.turn >= self.config.max_turns:
            state.error = "达到最大轮次限制"
            logger.warning(f"触发保护: {state.error}")
            return True
        
        # 总超时
        elapsed = time.time() - state.start_time
        if elapsed >= self.config.timeout_seconds:
            state.error = f"任务超时 ({elapsed:.1f}s >= {self.config.timeout_seconds}s)"
            logger.warning(f"触发保护: {state.error}")
            return True
        
        return False
    
    def _get_fallback_response(self, state: LoopState) -> str:
        """降级响应"""
        if state.error:
            return f"任务未能完成：{state.error}。请简化任务后重试。"
        return "任务处理超时，请稍后再试。"
