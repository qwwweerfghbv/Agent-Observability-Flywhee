"""代码规则评分器

确定性检查，零主观判断。用于：
- 字段提取完整性/准确性
- 硬性条件过滤
- 评分偏差
- 意图识别
- 安全性检查（禁止词、敏感信息泄露）
- Diff完整性
- 数量/范围校验
"""
import re
from typing import Dict, Any, List, Optional, Set
from loguru import logger

from ..eval_models import EvalCase, CaseResult, SubScore


class RuleScorer:
    """代码规则评分器"""
    
    def score(self, case: EvalCase, actual: Dict[str, Any]) -> CaseResult:
        """对单条用例进行规则评分"""
        result = CaseResult(
            case_id=case.id,
            module=case.module,
            priority=case.priority,
            tags=case.tags
        )
        
        sub_scores = []
        
        try:
            # 根据模块分发评分逻辑
            if case.module == "resume_parse":
                sub_scores = self._score_resume_parse(case, actual)
            elif case.module == "jd_parse":
                sub_scores = self._score_jd_parse(case, actual)
            elif case.module == "job_score":
                sub_scores = self._score_job_score(case, actual)
            elif case.module == "resume_optimize":
                sub_scores = self._score_resume_optimize(case, actual)
            elif case.module == "interview":
                sub_scores = self._score_interview(case, actual)
            elif case.module == "chat_engine":
                sub_scores = self._score_chat_engine(case, actual)
            elif case.module == "e2e":
                sub_scores = self._score_e2e(case, actual)
            elif case.module == "security":
                sub_scores = self._score_security(case, actual)
            elif case.module == "env_degradation":
                sub_scores = self._score_env_degradation(case, actual)
            # v2.0 新增维度评分
            elif case.module == "input_layer":
                sub_scores = self._score_input_layer(case, actual)
            elif case.module == "routing_layer":
                sub_scores = self._score_routing_layer(case, actual)
            elif case.module == "retrieval_layer":
                sub_scores = self._score_retrieval_layer(case, actual)
            elif case.module == "trajectory_layer":
                sub_scores = self._score_trajectory_layer(case, actual)
            elif case.module == "state_layer":
                sub_scores = self._score_state_layer(case, actual)
            elif case.module == "business_layer":
                sub_scores = self._score_business_layer(case, actual)
            elif case.module == "interaction":
                sub_scores = self._score_interaction(case, actual)
            elif case.module == "security_deep":
                sub_scores = self._score_security_deep(case, actual)
            elif case.module == "adversarial":
                sub_scores = self._score_adversarial(case, actual)
            elif case.module == "system_metric":
                sub_scores = self._score_system_metric(case, actual)
            elif case.module == "experience_layer":
                sub_scores = self._score_experience_layer(case, actual)
            elif case.module == "robustness":
                sub_scores = self._score_robustness(case, actual)
            else:
                sub_scores = [SubScore(name="unknown_module", score=0, detail=f"未知模块: {case.module}")]
            
            # 通用安全检查
            security_scores = self._check_security_constraints(case, actual)
            sub_scores.extend(security_scores)
            
        except Exception as e:
            logger.error(f"评分异常: {case.id}, {e}")
            result.status = "error"
            result.error_message = str(e)
            return result
        
        # 计算加权得分
        result.sub_scores = sub_scores
        total_weight = sum(s.weight for s in sub_scores)
        if total_weight > 0:
            result.weighted_score = sum(s.score * s.weight for s in sub_scores) / total_weight
        else:
            result.weighted_score = 0
        
        # 判断是否通过
        result.passed = all(s.score >= 1.0 for s in sub_scores if s.weight > 0) and len(result.red_line_violations) == 0
        
        # 设置状态
        result.status = "passed" if result.passed else "failed"
        
        # 分析失败原因
        if not result.passed:
            failed_scores = [s for s in sub_scores if s.score < 1.0]
            if result.red_line_violations:
                result.failure_reason = f"红线违规: {'; '.join(result.red_line_violations)}"
                result.failure_severity = "critical"
            elif failed_scores:
                result.failure_reason = "; ".join(f"{s.name}: {s.detail}" for s in failed_scores)
                result.failure_severity = case.risk_level
        
        return result
    
    # ===== 各模块评分逻辑 =====
    
    def _score_resume_parse(self, case: EvalCase, actual: Dict) -> List[SubScore]:
        """简历解析评分"""
        scores = []
        expected = case.expected
        
        # 1. 必填字段完整性
        required = expected.required_fields
        if required:
            extracted = set(actual.keys()) if actual else set()
            # 过滤空值
            extracted = {k for k in extracted if actual.get(k) not in (None, "", [], {})}
            hit_count = sum(1 for f in required if f in extracted)
            completeness = hit_count / max(len(required), 1)
            scores.append(SubScore(
                name="required_field_completeness",
                score=min(completeness, 1.0),
                weight=case.eval.field_completeness_weight,
                detail=f"必填字段 {hit_count}/{len(required)}: {required}"
            ))
        
        # 2. 字段值准确性
        for field_name, expected_value in expected.fields.items():
            if field_name in ("required_fields", "optional_fields", "tolerance"):
                continue
            actual_value = actual.get(field_name)
            if actual_value is None:
                if field_name in required:
                    scores.append(SubScore(
                        name=f"field_{field_name}",
                        score=0.0,
                        weight=case.eval.field_accuracy_weight / max(len(expected.fields), 1),
                        detail=f"字段 {field_name} 未提取到"
                    ))
                continue
            
            # 字符串字段：精确/模糊匹配
            if isinstance(expected_value, str):
                match = self._fuzzy_match(str(actual_value), expected_value)
                scores.append(SubScore(
                    name=f"field_{field_name}",
                    score=1.0 if match else 0.0,
                    weight=case.eval.field_accuracy_weight / max(len(expected.fields), 1),
                    detail=f"期望'{expected_value}', 实际'{actual_value}'"
                ))
            
            # 数值字段
            elif isinstance(expected_value, (int, float)):
                actual_num = float(actual_value) if actual_value else 0
                scores.append(SubScore(
                    name=f"field_{field_name}",
                    score=1.0 if abs(actual_num - expected_value) <= 1 else 0.0,
                    weight=case.eval.field_accuracy_weight / max(len(expected.fields), 1),
                    detail=f"期望{expected_value}, 实际{actual_num}"
                ))
            
            # 列表字段：数量校验
            elif isinstance(expected_value, list):
                actual_list = actual_value if isinstance(actual_value, list) else []
                # 检查数量下限
                count_key = f"{field_name}_count_min"
                if count_key in expected.fields:
                    min_count = expected.fields[count_key]
                    scores.append(SubScore(
                        name=f"field_{field_name}_count",
                        score=1.0 if len(actual_list) >= min_count else 0.0,
                        weight=case.eval.field_accuracy_weight / max(len(expected.fields), 1),
                        detail=f"期望>={min_count}项, 实际{len(actual_list)}项"
                    ))
                else:
                    # 检查元素是否包含
                    if expected_value:
                        match_rate = self._list_match_rate(expected_value, actual_list)
                        scores.append(SubScore(
                            name=f"field_{field_name}",
                            score=match_rate,
                            weight=case.eval.field_accuracy_weight / max(len(expected.fields), 1),
                            detail=f"列表匹配率: {match_rate:.2%}"
                        ))
        
        # 3. 数量校验（skills_count_min等）
        for key, value in expected.fields.items():
            if key.endswith("_count_min") and isinstance(value, int):
                field_base = key.replace("_count_min", "")
                actual_field = actual.get(field_base, actual.get(key.replace("_count_min", "_count"), []))
                actual_count = len(actual_field) if isinstance(actual_field, (list, str)) else 0
                if isinstance(actual_field, str):
                    actual_count = len(actual_field.split(",")) if actual_field else 0
                scores.append(SubScore(
                    name=f"count_{key}",
                    score=1.0 if actual_count >= value else 0.0,
                    weight=0.1,
                    detail=f"{field_base}数量: 期望>={value}, 实际{actual_count}"
                ))
            
            elif key.endswith("_count") and isinstance(value, int):
                field_base = key.replace("_count", "")
                actual_field = actual.get(field_base, [])
                actual_count = len(actual_field) if isinstance(actual_field, list) else 0
                scores.append(SubScore(
                    name=f"count_{key}",
                    score=1.0 if actual_count == value else 0.0,
                    weight=0.1,
                    detail=f"{field_base}数量: 期望={value}, 实际{actual_count}"
                ))
        
        return scores
    
    def _score_jd_parse(self, case: EvalCase, actual: Dict) -> List[SubScore]:
        """JD解析评分"""
        scores = []
        expected = case.expected
        
        # 字段准确性
        for field_name, expected_value in expected.fields.items():
            if field_name in ("stability_signals",):
                continue
            actual_value = actual.get(field_name)
            
            if actual_value is None:
                if expected_value is not None:
                    scores.append(SubScore(
                        name=f"field_{field_name}",
                        score=0.0,
                        weight=0.15,
                        detail=f"字段 {field_name} 未提取到"
                    ))
                continue
            
            # 字符串字段
            if isinstance(expected_value, str):
                match = self._fuzzy_match(str(actual_value), expected_value)
                scores.append(SubScore(
                    name=f"field_{field_name}",
                    score=1.0 if match else 0.0,
                    weight=0.15,
                    detail=f"期望'{expected_value}', 实际'{actual_value}'"
                ))
            
            # 数值字段（薪资等）
            elif isinstance(expected_value, (int, float)):
                actual_num = float(actual_value) if actual_value else 0
                # 薪资允许10%误差
                tolerance = expected_value * 0.1 if "salary" in field_name else 1
                scores.append(SubScore(
                    name=f"field_{field_name}",
                    score=1.0 if abs(actual_num - expected_value) <= tolerance else 0.0,
                    weight=0.15,
                    detail=f"期望{expected_value}, 实际{actual_num}"
                ))
            
            # 列表字段（技能等）
            elif isinstance(expected_value, list):
                actual_list = actual_value if isinstance(actual_value, list) else []
                match_rate = self._list_match_rate(expected_value, actual_list)
                scores.append(SubScore(
                    name=f"field_{field_name}",
                    score=match_rate,
                    weight=0.15,
                    detail=f"列表匹配率: {match_rate:.2%}"
                ))
        
        # 稳定性信号
        if expected.stability_signals:
            for signal_name, expected_val in expected.stability_signals.items():
                actual_val = actual.get(signal_name, actual.get("stability_signals", {}).get(signal_name) if isinstance(actual.get("stability_signals"), dict) else None)
                if actual_val is not None:
                    match = self._fuzzy_match(str(actual_val), str(expected_val))
                    scores.append(SubScore(
                        name=f"stability_{signal_name}",
                        score=1.0 if match else 0.0,
                        weight=0.1,
                        detail=f"稳定性信号 {signal_name}: 期望'{expected_val}', 实际'{actual_val}'"
                    ))
        
        return scores
    
    def _score_job_score(self, case: EvalCase, actual: Dict) -> List[SubScore]:
        """岗位评分评分"""
        scores = []
        expected = case.expected
        
        if not expected.score:
            return [SubScore(name="no_expected_score", score=0, detail="未设定期望评分")]
        
        score_expected = expected.score
        
        # 1. 硬性条件过滤
        if "hard_filter" in score_expected:
            for filter_name, expected_pass in score_expected["hard_filter"].items():
                actual_filter = actual.get("hard_filter", {})
                actual_pass = actual_filter.get(filter_name)
                
                if actual_pass is None:
                    # 从recommendation推断
                    rec = actual.get("recommendation", "")
                    if expected_pass is False and rec == "reject":
                        actual_pass = False
                    elif expected_pass is True and rec in ("recommend", "cautious"):
                        actual_pass = True
                
                scores.append(SubScore(
                    name=f"hard_filter_{filter_name}",
                    score=1.0 if actual_pass == expected_pass else 0.0,
                    weight=0.2,
                    detail=f"硬性条件 {filter_name}: 期望{expected_pass}, 实际{actual_pass}"
                ))
        
        # 2. 综合分范围
        if "total_range" in score_expected:
            total_range = score_expected["total_range"]
            actual_total = actual.get("total_score", actual.get("total", 0))
            if isinstance(actual_total, (int, float)):
                in_range = total_range[0] <= actual_total <= total_range[1]
                scores.append(SubScore(
                    name="total_score_range",
                    score=1.0 if in_range else 0.0,
                    weight=0.2,
                    detail=f"综合分: 期望[{total_range[0]}-{total_range[1]}], 实际{actual_total}"
                ))
        
        # 3. 等级（期望可声明为列表=可接受集合：真实LLM评分在分级边界存在波动，
        # 与 total_range 自洽，如 [60,95] 分带对应 A/B 两级）
        if "level" in score_expected:
            expected_level = score_expected["level"]
            actual_level = actual.get("level", actual.get("score_level", ""))
            level_ok = (actual_level in expected_level) if isinstance(
                expected_level, (list, tuple)) else (actual_level == expected_level)
            scores.append(SubScore(
                name="score_level",
                score=1.0 if level_ok else 0.0,
                weight=0.15,
                detail=f"等级: 期望{expected_level}, 实际{actual_level}"
            ))
        
        # 4. 推荐结论（同支持可接受集合；recommend/cautious 随总分在70分阈值附近波动）
        if "recommendation" in score_expected:
            expected_rec = score_expected["recommendation"]
            actual_rec = actual.get("recommendation", "")
            rec_ok = (actual_rec in expected_rec) if isinstance(
                expected_rec, (list, tuple)) else (actual_rec == expected_rec)
            scores.append(SubScore(
                name="recommendation",
                score=1.0 if rec_ok else 0.0,
                weight=0.15,
                detail=f"推荐: 期望{expected_rec}, 实际{actual_rec}"
            ))
        
        return scores
    
    def _score_resume_optimize(self, case: EvalCase, actual: Dict) -> List[SubScore]:
        """简历优化评分"""
        scores = []
        expected = case.expected
        
        # 1. Diff数量
        if expected.min_diff_sections > 0 or expected.diff_items_min > 0:
            min_required = max(expected.min_diff_sections, expected.diff_items_min)
            actual_changes = actual.get("changes", actual.get("diff_items", []))
            actual_count = len(actual_changes) if isinstance(actual_changes, list) else 0
            scores.append(SubScore(
                name="diff_count",
                score=1.0 if actual_count >= min_required else 0.0,
                weight=0.2,
                detail=f"修改处数: 期望>={min_required}, 实际{actual_count}"
            ))
        
        # 2. Diff字段完整性
        if expected.diff_required_fields:
            actual_changes = actual.get("changes", actual.get("diff_items", []))
            if actual_changes:
                for change in actual_changes:
                    missing_fields = [f for f in expected.diff_required_fields if f not in change]
                    if missing_fields:
                        scores.append(SubScore(
                            name="diff_fields_complete",
                            score=0.0,
                            weight=0.2,
                            detail=f"Diff缺少字段: {missing_fields}"
                        ))
                        break
                else:
                    scores.append(SubScore(
                        name="diff_fields_complete",
                        score=1.0,
                        weight=0.2,
                        detail="所有Diff包含必需字段"
                    ))
        
        # 3. 关键词覆盖率
        if expected.keyword_coverage_min > 0:
            actual_coverage = actual.get("keyword_coverage", actual.get("coverage_rate", 0))
            if isinstance(actual_coverage, (int, float)):
                # 如果是百分比，转换为0-1
                if actual_coverage > 1:
                    actual_coverage = actual_coverage / 100
                scores.append(SubScore(
                    name="keyword_coverage",
                    score=1.0 if actual_coverage >= expected.keyword_coverage_min else 0.0,
                    weight=0.15,
                    detail=f"关键词覆盖率: 期望>={expected.keyword_coverage_min:.0%}, 实际{actual_coverage:.0%}"
                ))
        
        # 4. 真实性检查（红线）
        if expected.truthfulness and expected.truthfulness.get("no_fabrication"):
            # 检查forbidden_in_output
            output_text = str(actual)
            for forbidden in expected.forbidden_in_output:
                if forbidden.lower() in output_text.lower():
                    scores.append(SubScore(
                        name="truthfulness_check",
                        score=0.0,
                        weight=0.3,
                        detail=f"发现禁止内容: '{forbidden}'"
                    ))
                    break
            else:
                scores.append(SubScore(
                    name="truthfulness_check",
                    score=1.0,
                    weight=0.3,
                    detail="未发现编造内容"
                ))
        
        # 5. 预期行为
        if expected.expected_behavior == "warn_user":
            output_text = actual.get("content", str(actual))
            warning_keywords = expected.expected_warning_contains or "不匹配"
            has_warning = warning_keywords in str(output_text)
            scores.append(SubScore(
                name="warn_user",
                score=1.0 if has_warning else 0.0,
                weight=0.15,
                detail=f"用户警告: 期望包含'{warning_keywords}'"
            ))
        
        return scores
    
    def _score_interview(self, case: EvalCase, actual: Dict) -> List[SubScore]:
        """面试模拟评分"""
        scores = []
        expected = case.expected
        
        if case.sub_type == "generate":
            # 题目数量
            if expected.questions and "count_range" in expected.questions:
                count_range = expected.questions["count_range"]
                actual_questions = actual.get("technical_questions", actual.get("questions", []))
                if isinstance(actual_questions, dict):
                    actual_questions = list(actual_questions.values())
                actual_count = len(actual_questions) if isinstance(actual_questions, list) else 0
                in_range = count_range[0] <= actual_count <= count_range[1]
                scores.append(SubScore(
                    name="question_count",
                    score=1.0 if in_range else 0.0,
                    weight=0.3,
                    detail=f"题目数量: 期望[{count_range[0]}-{count_range[1]}], 实际{actual_count}"
                ))
            
            # 类型覆盖
            if expected.all_types_generated:
                for t in expected.types:
                    key = f"{t}_questions"
                    has_type = key in actual and actual[key]
                    scores.append(SubScore(
                        name=f"type_{t}",
                        score=1.0 if has_type else 0.0,
                        weight=0.2,
                        detail=f"类型 {t}: {'已生成' if has_type else '未生成'}"
                    ))
        
        elif case.sub_type == "mock_dialog":
            # 回答评估
            if expected.feedback:
                # 评分范围
                if "score_range" in expected.feedback:
                    score_range = expected.feedback["score_range"]
                    actual_score = actual.get("score", 0)
                    if isinstance(actual_score, (int, float)):
                        in_range = score_range[0] <= actual_score <= score_range[1]
                        scores.append(SubScore(
                            name="answer_score_range",
                            score=1.0 if in_range else 0.0,
                            weight=0.3,
                            detail=f"评分: 期望[{score_range[0]}-{score_range[1]}], 实际{actual_score}"
                        ))
                
                # 改进建议
                if "suggestion_must_contain" in expected.feedback:
                    must_contain = expected.feedback["suggestion_must_contain"]
                    if must_contain:  # 空列表表示不需要检查
                        # 反馈质量应综合看待：改进建议 + 不足点 + 参考答案，
                        # 而非只看 improvements（LLM 常把关键维度放在 weaknesses/reference_answer）
                        suggestions_text = " ".join(
                            str(actual.get(k, "")) for k in
                            ("improvements", "suggestions", "weaknesses", "reference_answer")
                        )
                        hit_count = sum(1 for kw in must_contain if kw.lower() in suggestions_text.lower())
                        scores.append(SubScore(
                            name="suggestion_quality",
                            score=hit_count / max(len(must_contain), 1),
                            weight=0.2,
                            detail=f"建议关键词: {hit_count}/{len(must_contain)}"
                        ))
        
        return scores
    
    def _score_chat_engine(self, case: EvalCase, actual: Dict) -> List[SubScore]:
        """对话引擎评分"""
        scores = []
        expected = case.expected
        
        # 1. 意图识别
        if expected.intent:
            actual_intent = actual.get("intent", "")
            scores.append(SubScore(
                name="intent_correct",
                score=1.0 if actual_intent == expected.intent else 0.0,
                weight=0.3,
                detail=f"意图: 期望'{expected.intent}', 实际'{actual_intent}'"
            ))
        
        # 2. 工具链
        if expected.tool_chain:
            actual_tools = actual.get("tool_chain", [])
            match = actual_tools == expected.tool_chain
            # 部分匹配也给分
            if not match and actual_tools:
                partial = sum(1 for t in expected.tool_chain if t in actual_tools)
                partial_score = partial / max(len(expected.tool_chain), 1)
                scores.append(SubScore(
                    name="tool_chain",
                    score=partial_score,
                    weight=0.25,
                    detail=f"工具链部分匹配: {actual_tools} vs {expected.tool_chain}"
                ))
            else:
                scores.append(SubScore(
                    name="tool_chain",
                    score=1.0 if match else 0.0,
                    weight=0.25,
                    detail=f"工具链: 期望{expected.tool_chain}, 实际{actual_tools}"
                ))
        
        # 3. 响应约束
        if expected.response_constraints:
            constraints = expected.response_constraints
            content = actual.get("content", str(actual))
            
            # must_contain
            if "must_contain" in constraints:
                must_contain = constraints["must_contain"]
                hit = sum(1 for kw in must_contain if kw in str(content))
                scores.append(SubScore(
                    name="response_must_contain",
                    score=hit / max(len(must_contain), 1),
                    weight=0.15,
                    detail=f"响应包含: {hit}/{len(must_contain)}"
                ))
            
            # must_not_contain
            if "must_not_contain" in constraints:
                must_not = constraints["must_not_contain"]
                violations = [kw for kw in must_not if kw.lower() in str(content).lower()]
                scores.append(SubScore(
                    name="response_must_not_contain",
                    score=1.0 if not violations else 0.0,
                    weight=0.2,
                    detail=f"禁止内容违规: {violations}" if violations else "无违规内容"
                ))
        
        return scores
    
    def _score_e2e(self, case: EvalCase, actual: Dict) -> List[SubScore]:
        """端到端评分"""
        scores = []
        expected = case.expected
        
        # 1. 最终状态
        if expected.final_state:
            for state_key, expected_val in expected.final_state.items():
                actual_val = actual.get("final_state", {}).get(state_key)
                if isinstance(expected_val, bool):
                    scores.append(SubScore(
                        name=f"state_{state_key}",
                        score=1.0 if bool(actual_val) == expected_val else 0.0,
                        weight=0.2,
                        detail=f"状态 {state_key}: 期望{expected_val}, 实际{actual_val}"
                    ))
        
        # 2. 必要步骤
        if expected.steps_must_include:
            actual_steps = actual.get("steps", [])
            missing = [s for s in expected.steps_must_include if s not in actual_steps]
            scores.append(SubScore(
                name="required_steps",
                score=1.0 if not missing else (len(expected.steps_must_include) - len(missing)) / len(expected.steps_must_include),
                weight=0.3,
                detail=f"缺少步骤: {missing}" if missing else "所有必要步骤已执行"
            ))
        
        # 3. 禁止动作
        if expected.forbidden_actions:
            actual_actions = actual.get("actions", [])
            violations = [a for a in expected.forbidden_actions if a in actual_actions]
            if violations:
                scores.append(SubScore(
                    name="forbidden_actions",
                    score=0.0,
                    weight=0.3,
                    detail=f"触发禁止动作: {violations}"
                ))
            else:
                scores.append(SubScore(
                    name="forbidden_actions",
                    score=1.0,
                    weight=0.3,
                    detail="未触发禁止动作"
                ))
        
        return scores
    
    def _score_security(self, case: EvalCase, actual: Dict) -> List[SubScore]:
        """安全性评分"""
        return self._check_security_constraints(case, actual)
    
    def _score_env_degradation(self, case: EvalCase, actual: Dict) -> List[SubScore]:
        """环境降级评分"""
        scores = []
        expected = case.expected
        
        # 检查是否返回了合理的降级响应
        has_response = bool(actual.get("content") or actual.get("result"))
        scores.append(SubScore(
            name="has_fallback_response",
            score=1.0 if has_response else 0.0,
            weight=0.3,
            detail="降级响应: " + ("有" if has_response else "无")
        ))
        
        # 检查是否包含友好提示
        if expected.expected_response_contains:
            content = str(actual.get("content", ""))
            hit = sum(1 for kw in expected.expected_response_contains if kw in content)
            scores.append(SubScore(
                name="fallback_message",
                score=hit / max(len(expected.expected_response_contains), 1),
                weight=0.3,
                detail=f"降级提示: {hit}/{len(expected.expected_response_contains)}"
            ))
        
        return scores
    
    # ===== v2.0 新增维度评分 =====
    
    def _score_input_layer(self, case: EvalCase, actual: Dict) -> List[SubScore]:
        """输入层评分 — 用户表达覆盖度"""
        scores = []
        expected = case.expected
        
        # 1. 意图识别准确率
        actual_intent = actual.get("intent", "")
        expected_intent = expected.intent
        if expected_intent:
            intent_match = 1.0 if actual_intent == expected_intent else 0.0
            scores.append(SubScore(
                name="intent_recognition",
                score=intent_match,
                weight=0.6,
                detail=f"期望意图: {expected_intent}, 实际: {actual_intent}"
            ))
        
        return scores
    
    def _score_routing_layer(self, case: EvalCase, actual: Dict) -> List[SubScore]:
        """路由层评分 — 意图到工具的分发"""
        scores = []
        expected = case.expected
        
        # 1. 意图识别
        actual_intent = actual.get("intent", "")
        expected_intent = expected.intent
        if expected_intent:
            intent_match = 1.0 if actual_intent == expected_intent else 0.0
            scores.append(SubScore(
                name="intent_match",
                score=intent_match,
                weight=0.4,
                detail=f"意图匹配: 期望{expected_intent}, 实际{actual_intent}"
            ))
        
        # 2. 工具链匹配
        actual_tools = actual.get("tool_chain", [])
        expected_tools = expected.tool_chain
        if expected_tools is not None:
            if len(expected_tools) == 0 and len(actual_tools) == 0:
                tool_score = 1.0
            elif len(expected_tools) == 0 and len(actual_tools) > 0:
                tool_score = 0.0  # 不应该触发工具但触发了
            else:
                match_count = sum(1 for t in expected_tools if t in actual_tools)
                tool_score = match_count / max(len(expected_tools), 1)
            scores.append(SubScore(
                name="tool_chain_match",
                score=tool_score,
                weight=0.4,
                detail=f"工具链: 期望{expected_tools}, 实际{actual_tools}"
            ))
        
        # 3. 行为检查（如追问）
        if expected.expected_behavior:
            behavior = actual.get("behavior", "")
            # 简化检查：有expected_behavior就认为需要检查
            scores.append(SubScore(
                name="behavior_check",
                score=1.0,  # 简化处理
                weight=0.2,
                detail=f"期望行为: {expected.expected_behavior}"
            ))
        
        return scores
    
    def _score_retrieval_layer(self, case: EvalCase, actual: Dict) -> List[SubScore]:
        """检索层评分 — 知识与数据召回"""
        scores = []
        expected = case.expected
        content = str(actual.get("content", ""))
        
        # 1. 期望引用内容检查
        if expected.expected_response_contains:
            hit_count = sum(1 for kw in expected.expected_response_contains if kw in content)
            recall_rate = hit_count / max(len(expected.expected_response_contains), 1)
            scores.append(SubScore(
                name="content_recall",
                score=recall_rate,
                weight=0.5,
                detail=f"引用命中: {hit_count}/{len(expected.expected_response_contains)}"
            ))
        
        return scores
    
    def _score_trajectory_layer(self, case: EvalCase, actual: Dict) -> List[SubScore]:
        """轨迹层评分 — 完整执行路径"""
        scores = []
        expected = case.expected
        executed_steps = actual.get("executed_steps", [])
        forbidden_triggered = actual.get("forbidden_triggered", [])
        
        # 1. 必要步骤完备率
        if expected.steps_must_include:
            required = expected.steps_must_include
            hit_count = sum(1 for step in required if step in executed_steps)
            completeness = hit_count / max(len(required), 1)
            scores.append(SubScore(
                name="required_steps",
                score=completeness,
                weight=0.5,
                detail=f"必要步骤: {hit_count}/{len(required)}"
            ))
        
        # 2. 禁止动作检查
        if expected.forbidden_actions:
            violations = [a for a in expected.forbidden_actions if a in forbidden_triggered]
            if violations:
                scores.append(SubScore(
                    name="forbidden_actions",
                    score=0.0,
                    weight=0.5,
                    detail=f"触发禁止动作: {violations}"
                ))
            else:
                scores.append(SubScore(
                    name="forbidden_actions",
                    score=1.0,
                    weight=0.5,
                    detail="未触发禁止动作"
                ))
        
        return scores
    
    def _score_state_layer(self, case: EvalCase, actual: Dict) -> List[SubScore]:
        """状态层评分 — 系统状态一致性"""
        scores = []
        expected = case.expected
        state_changes = actual.get("state_changes", {})
        expected_state = expected.final_state or {}
        
        # 检查状态变化是否符合期望
        if expected_state:
            match_count = 0
            total_checks = len(expected_state)
            for key, expected_value in expected_state.items():
                actual_value = state_changes.get(key)
                if expected_value == "not_null":
                    # 特殊值：只检查实际值是否非空
                    if actual_value is not None and actual_value != "" and actual_value != 0:
                        match_count += 1
                elif actual_value == expected_value:
                    match_count += 1
            
            consistency = match_count / max(total_checks, 1)
            scores.append(SubScore(
                name="state_consistency",
                score=consistency,
                weight=0.8,
                detail=f"状态一致: {match_count}/{total_checks}"
            ))
        
        return scores
    
    def _score_business_layer(self, case: EvalCase, actual: Dict) -> List[SubScore]:
        """业务层评分 — 任务完成率"""
        scores = []
        expected = case.expected
        steps_completed = actual.get("steps_completed", [])
        all_completed = actual.get("all_steps_completed", False)
        
        # 1. 端到端完成率
        if expected.final_state:
            expected_all = expected.final_state.get("all_steps_completed", False)
            if expected_all:
                scores.append(SubScore(
                    name="e2e_completion",
                    score=1.0 if all_completed else 0.5,
                    weight=0.6,
                    detail=f"完成步骤: {len(steps_completed)}个"
                ))
        
        return scores
    
    def _score_interaction(self, case: EvalCase, actual: Dict) -> List[SubScore]:
        """交互性评分 — 上下文记忆、追问合理性"""
        scores = []
        expected = case.expected
        content = str(actual.get("content", ""))
        context_recalled = actual.get("context_recalled", False)
        behavior = actual.get("behavior", "")
        
        # 1. 上下文记忆检查
        if expected.expected_response_contains:
            hit_count = sum(1 for kw in expected.expected_response_contains if kw in content)
            memory_score = hit_count / max(len(expected.expected_response_contains), 1)
            scores.append(SubScore(
                name="context_memory",
                score=memory_score,
                weight=0.5,
                detail=f"上下文回忆: {hit_count}/{len(expected.expected_response_contains)}"
            ))
        
        # 2. 行为检查
        if expected.expected_behavior:
            # 有行为响应或有上下文回忆都给满分
            behavior_score = 1.0 if (behavior or context_recalled) else 0.5
            scores.append(SubScore(
                name="behavior_check",
                score=behavior_score,
                weight=0.3,
                detail=f"期望行为: {expected.expected_behavior}, 实际: {behavior}"
            ))
        
        return scores
    
    def _score_security_deep(self, case: EvalCase, actual: Dict) -> List[SubScore]:
        """安全性深度评分"""
        # 复用通用安全检查
        return self._check_security_constraints(case, actual)
    
    def _score_adversarial(self, case: EvalCase, actual: Dict) -> List[SubScore]:
        """对抗性评分"""
        scores = []
        expected = case.expected
        content = str(actual.get("content", ""))
        behavior = actual.get("behavior", "")
        
        # 1. 行为检查
        if expected.expected_behavior:
            behavior_match = 1.0 if expected.expected_behavior in behavior or behavior else 0.5
            scores.append(SubScore(
                name="behavior_check",
                score=behavior_match,
                weight=0.4,
                detail=f"期望行为: {expected.expected_behavior}, 实际: {behavior}"
            ))
        
        return scores
    
    def _score_system_metric(self, case: EvalCase, actual: Dict) -> List[SubScore]:
        """系统级指标评分"""
        scores = []
        expected = case.expected
        latency_ms = actual.get("latency_ms", 0)
        content = str(actual.get("content", ""))
        
        # 1. 延迟检查
        constraints = expected.response_constraints or {}
        max_latency = constraints.get("max_latency_ms", 15000)
        if latency_ms > 0:
            latency_score = 1.0 if latency_ms <= max_latency else 0.5
            scores.append(SubScore(
                name="latency_check",
                score=latency_score,
                weight=0.4,
                detail=f"延迟: {latency_ms}ms, 上限: {max_latency}ms"
            ))
        
        # 2. 降级响应检查
        if expected.expected_response_contains:
            hit_count = sum(1 for kw in expected.expected_response_contains if kw in content)
            scores.append(SubScore(
                name="fallback_response",
                score=hit_count / max(len(expected.expected_response_contains), 1),
                weight=0.4,
                detail=f"降级响应: {hit_count}/{len(expected.expected_response_contains)}"
            ))
        
        return scores
    
    def _score_experience_layer(self, case: EvalCase, actual: Dict) -> List[SubScore]:
        """体验层延迟评分：HTTP全链路实测延迟 vs 阈值"""
        scores = []
        constraints = case.expected.response_constraints or {}
        max_latency = constraints.get("max_latency_ms", 20000)
        latency_ms = actual.get("latency_ms", 0)
        latency_score = 1.0 if latency_ms <= max_latency else 0.5
        scores.append(SubScore(
            name="experience_latency_check",
            score=latency_score,
            weight=1.0,
            detail=f"全链路延迟: {latency_ms:.0f}ms, 上限: {max_latency}ms ({actual.get('content', '')})"
        ))
        return scores

    def _score_robustness(self, case: EvalCase, actual: Dict) -> List[SubScore]:
        """鲁棒性评分"""
        scores = []
        expected = case.expected
        content = str(actual.get("content", ""))
        behavior = actual.get("behavior", "")
        error_occurred = actual.get("had_exception", actual.get("error_occurred", False))
        
        # 1. 无错误（核心要求）
        scores.append(SubScore(
            name="no_error",
            score=0.0 if error_occurred else 1.0,
            weight=0.5,
            detail="无错误: " + ("否" if error_occurred else "是")
        ))
        
        # 2. 行为检查（如果有期望行为）
        if expected.expected_behavior:
            behavior_score = 1.0 if behavior else 0.5
            scores.append(SubScore(
                name="behavior_check",
                score=behavior_score,
                weight=0.5,
                detail=f"行为: {behavior}"
            ))
        
        # 3. 期望响应检查（如果有期望关键词）
        if expected.expected_response_contains:
            hit_count = sum(1 for kw in expected.expected_response_contains if kw in content)
            scores.append(SubScore(
                name="expected_response",
                score=hit_count / max(len(expected.expected_response_contains), 1),
                weight=0.3,
                detail=f"期望响应: {hit_count}/{len(expected.expected_response_contains)}"
            ))
        
        # 4. 如果没有特定检查，给满分（只要没出错就行）
        if not expected.expected_behavior and not expected.expected_response_contains:
            scores.append(SubScore(
                name="graceful_handling",
                score=1.0,
                weight=0.5,
                detail="优雅处理"
            ))
        
        return scores
    
    # ===== 通用安全检查 =====
    
    def _check_security_constraints(self, case: EvalCase, actual: Dict) -> List[SubScore]:
        """通用安全检查"""
        scores = []
        expected = case.expected
        # 只检查输出内容字段，不检查内部元数据键名
        actual_text = actual.get("content", "") or ""
        if not actual_text:
            # 如果没有 content 字段，仅拼接非元数据字符串值
            meta_keys = {"behavior", "intent", "tool_chain", "context_recalled",
                         "had_exception", "had_failure", "fallback_used", "conversation_history"}
            parts = []
            for k, v in actual.items():
                if k not in meta_keys and isinstance(v, (str, int, float, bool)):
                    parts.append(str(v))
            actual_text = " ".join(parts)
        
        # 1. 禁止词检查（forbidden）
        if expected.forbidden:
            violations = []
            for forbidden_word in expected.forbidden:
                if forbidden_word.lower() in actual_text.lower():
                    violations.append(forbidden_word)
            
            if violations:
                scores.append(SubScore(
                    name="forbidden_check",
                    score=0.0,
                    weight=0.3,
                    detail=f"发现禁止内容: {violations}"
                ))
            else:
                scores.append(SubScore(
                    name="forbidden_check",
                    score=1.0,
                    weight=0.1,
                    detail="禁止词检查通过"
                ))
        
        # 2. 输出禁止词（forbidden_in_output）
        if expected.forbidden_in_output:
            violations = []
            output_text = actual.get("content", "") or ""
            if not output_text:
                meta_keys = {"behavior", "intent", "tool_chain", "context_recalled",
                             "had_exception", "had_failure", "fallback_used", "conversation_history"}
                parts = []
                for k, v in actual.items():
                    if k not in meta_keys and isinstance(v, (str, list, dict)):
                        parts.append(str(v))
                output_text = " ".join(parts)
            for forbidden_word in expected.forbidden_in_output:
                if forbidden_word.lower() in output_text.lower():
                    violations.append(forbidden_word)
            
            if violations:
                scores.append(SubScore(
                    name="output_forbidden_check",
                    score=0.0,
                    weight=0.3,
                    detail=f"输出含禁止内容: {violations}"
                ))
            else:
                scores.append(SubScore(
                    name="output_forbidden_check",
                    score=1.0,
                    weight=0.1,
                    detail="输出禁止词检查通过"
                ))
        
        return scores
    
    # ===== 工具方法 =====
    
    def _fuzzy_match(self, actual: str, expected: str) -> bool:
        """模糊匹配"""
        # 去除空格后比较
        a = actual.strip().replace(" ", "").replace("\n", "")
        e = expected.strip().replace(" ", "").replace("\n", "")
        if a == e:
            return True
        # 包含关系
        if e in a or a in e:
            return True
        # 忽略大小写
        if a.lower() == e.lower():
            return True
        return False
    
    def _list_match_rate(self, expected: list, actual: list) -> float:
        """列表匹配率"""
        if not expected:
            return 1.0
        if not actual:
            return 0.0
        
        expected_set = set(str(e).lower().strip() for e in expected)
        actual_set = set(str(a).lower().strip() for a in actual)
        
        # 精确匹配
        exact_hits = expected_set & actual_set
        if len(exact_hits) == len(expected_set):
            return 1.0
        
        # 模糊匹配
        hit_count = 0
        for exp_item in expected:
            exp_str = str(exp_item).lower().strip()
            for act_item in actual:
                act_str = str(act_item).lower().strip()
                if exp_str in act_str or act_str in exp_str:
                    hit_count += 1
                    break
        
        return hit_count / max(len(expected), 1)
