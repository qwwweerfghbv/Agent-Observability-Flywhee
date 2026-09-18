"""Reflection模块 - 自我检查与纠错

Agent执行后自我检查输出质量，发现问题可自动修正。
"""
from typing import Dict, List, Optional
from dataclasses import dataclass
from loguru import logger


@dataclass
class ReflectionResult:
    """反思结果"""
    quality_score: int = 0          # 质量分数 0-100
    is_complete: bool = False       # 是否完整
    has_issues: bool = False        # 是否有问题
    issues: List[str] = None        # 问题列表
    suggestions: List[str] = None   # 改进建议
    needs_retry: bool = False       # 是否需要重试
    
    def __post_init__(self):
        self.issues = self.issues or []
        self.suggestions = self.suggestions or []


class Reflection:
    """反思/自我纠错模块"""
    
    def __init__(self, llm_adapter=None, quality_threshold: int = 70):
        self.llm = llm_adapter
        self.quality_threshold = quality_threshold
        logger.info(f"Reflection初始化，质量阈值: {quality_threshold}")
    
    def evaluate(self, task: str, output: str, trajectory_summary: str = "") -> ReflectionResult:
        """评估Agent执行结果的质量"""
        if self.llm:
            return self._evaluate_with_llm(task, output, trajectory_summary)
        else:
            return self._evaluate_with_rules(task, output)
    
    def _evaluate_with_llm(self, task: str, output: str, trajectory_summary: str) -> ReflectionResult:
        """使用LLM评估质量"""
        from app.prompts.templates import PromptManager
        
        prompt = PromptManager.get(
            "reflection",
            original_task=task,
            agent_output=output[:2000],  # 限制长度
            trajectory_summary=trajectory_summary[:1000]
        )
        
        try:
            response = self.llm.chat([{"role": "user", "content": prompt}])
            # TODO: 解析LLM返回的JSON
            # 骨架阶段降级到规则评估
            logger.warning("LLM反思解析尚未实现，降级到规则评估")
            return self._evaluate_with_rules(task, output)
        except Exception as e:
            logger.error(f"LLM反思失败: {e}")
            return self._evaluate_with_rules(task, output)
    
    def _evaluate_with_rules(self, task: str, output: str) -> ReflectionResult:
        """使用规则评估质量（降级方案）"""
        issues = []
        suggestions = []
        score = 100
        
        # 检查1: 输出是否为空
        if not output or len(output.strip()) < 10:
            issues.append("输出内容过短或为空")
            score -= 50
        
        # 检查2: 是否包含错误标记
        if "错误" in output or "失败" in output or "无法" in output:
            issues.append("输出包含错误/失败标记")
            score -= 20
        
        # 检查3: 是否回应了任务关键词
        task_keywords = self._extract_keywords(task)
        output_lower = output.lower()
        matched = sum(1 for kw in task_keywords if kw in output_lower)
        if task_keywords and matched == 0:
            issues.append("输出未回应任务关键词")
            score -= 30
            suggestions.append("请确保输出包含任务相关的关键词")
        
        # 检查4: 输出长度合理性
        if len(output) > 10000:
            suggestions.append("输出过长，建议精简")
            score -= 10
        
        # 判断是否需要重试
        needs_retry = score < self.quality_threshold
        is_complete = len(issues) == 0
        
        result = ReflectionResult(
            quality_score=max(0, score),
            is_complete=is_complete,
            has_issues=len(issues) > 0,
            issues=issues,
            suggestions=suggestions,
            needs_retry=needs_retry
        )
        
        logger.info(f"反思评估: score={result.quality_score}, issues={len(issues)}, retry={needs_retry}")
        return result
    
    def _extract_keywords(self, text: str) -> List[str]:
        """从文本中提取关键词（简单实现）"""
        # 移除常见停用词
        stop_words = {"的", "了", "在", "是", "我", "有", "和", "就", "不", "人", "都", "一", "一个", "上", "也", "很", "到", "说", "要", "去", "你", "会", "着", "没有", "看", "好", "自己", "这"}
        
        # 简单分词（按空格和标点）
        import re
        words = re.findall(r'[\w\u4e00-\u9fa5]{2,}', text)
        
        # 过滤停用词
        keywords = [w for w in words if w not in stop_words and len(w) >= 2]
        
        # 去重，取前10个
        return list(set(keywords))[:10]
    
    def should_retry(self, result: ReflectionResult, retry_count: int, max_retries: int = 2) -> bool:
        """判断是否应该重试"""
        if not result.needs_retry:
            return False
        if retry_count >= max_retries:
            logger.warning(f"已达最大重试次数: {max_retries}")
            return False
        return True
    
    def generate_correction_prompt(self, task: str, output: str, issues: List[str]) -> str:
        """生成修正提示词"""
        issues_str = "\n".join(f"- {issue}" for issue in issues)
        
        return f"""请修正以下回答中的问题。

## 原始任务
{task}

## 当前回答
{output}

## 发现的问题
{issues_str}

## 要求
1. 针对每个问题进行修正
2. 保持回答的完整性
3. 不要引入新的问题

请输出修正后的完整回答。
"""
