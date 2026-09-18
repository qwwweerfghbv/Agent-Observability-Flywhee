"""评测飞轮机制

实现评估驱动开发的持续循环:
1. Bad Case 回流: 将失败用例自动收集到bad case库
2. 版本对比: 新旧版本用同一评测集跑分对比
3. 回归检测: 检测修复是否引入新问题
4. 评测集演化: 根据失败模式自动建议新增用例

飞轮: 定标准 → 开发 → 评估 → 灰度 → 监控 → 回流 → 更新标准 → 再开发
"""
import hashlib
import json
import os
import re
import time
from typing import List, Dict, Any, Optional, Callable, Tuple
from datetime import datetime
from pathlib import Path
from loguru import logger

from .eval_models import EvalReport, CaseResult, EvalCase


class BadCaseCollector:
    """Bad Case 收集器
    
    将评测失败的用例自动收集到bad case库，
    用于后续分析和回归测试。
    """
    
    def __init__(self, storage_dir: str = None):
        self.storage_dir = Path(storage_dir or "./tests/eval/results/bad_cases")
        self.storage_dir.mkdir(parents=True, exist_ok=True)
    
    def collect_from_report(self, report: EvalReport):
        """从评测报告中收集bad case"""
        bad_cases = []
        
        for result in report.case_results:
            if not result.passed and result.status != "skipped":
                bad_case = {
                    "case_id": result.case_id,
                    "module": result.module,
                    "priority": result.priority,
                    "tags": result.tags,
                    "status": result.status,
                    "failure_reason": result.failure_reason,
                    "failure_severity": result.failure_severity,
                    "red_line_violations": result.red_line_violations,
                    "actual_output": result.actual,
                    "latency_ms": result.latency_ms,
                    "timestamp": result.timestamp,
                    "run_id": report.run_id,
                    "agent_version": report.agent_version
                }
                bad_cases.append(bad_case)
        
        if bad_cases:
            # 保存到文件
            file_name = f"bad_cases_{report.run_id}.json"
            file_path = self.storage_dir / file_name
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(bad_cases, f, ensure_ascii=False, indent=2, default=str)
            
            logger.info(f"收集到 {len(bad_cases)} 条bad case，已保存到 {file_path}")
        
        return bad_cases
    
    def get_all_bad_cases(self, limit: int = 100) -> List[Dict]:
        """获取所有bad case"""
        all_cases = []
        for file in sorted(self.storage_dir.glob("bad_cases_*.json"), reverse=True):
            with open(file, "r", encoding="utf-8") as f:
                cases = json.load(f)
                all_cases.extend(cases)
                if len(all_cases) >= limit:
                    break
        return all_cases[:limit]
    
    def get_recurring_bad_cases(self, min_occurrences: int = 2) -> List[Dict]:
        """获取反复出现的bad case（高频失败）"""
        all_cases = self.get_all_bad_cases(limit=500)
        
        # 按case_id分组统计
        case_counts: Dict[str, List] = {}
        for case in all_cases:
            case_id = case["case_id"]
            if case_id not in case_counts:
                case_counts[case_id] = []
            case_counts[case_id].append(case)
        
        # 筛选反复出现的
        recurring = []
        for case_id, occurrences in case_counts.items():
            if len(occurrences) >= min_occurrences:
                recurring.append({
                    "case_id": case_id,
                    "occurrences": len(occurrences),
                    "latest": occurrences[0],
                    "failure_reasons": list(set(o.get("failure_reason", "") for o in occurrences))
                })
        
        recurring.sort(key=lambda x: x["occurrences"], reverse=True)
        return recurring


class VersionComparator:
    """版本对比器
    
    对比新旧版本的评测结果，量化每次改动的效果。
    """
    
    def __init__(self, results_dir: str = None):
        self.results_dir = Path(results_dir or "./tests/eval/results")
    
    def compare(self, old_run_id: str, new_run_id: str) -> Dict[str, Any]:
        """对比两个版本的评测结果"""
        old_report = self._load_report(old_run_id)
        new_report = self._load_report(new_run_id)
        
        if not old_report or not new_report:
            return {"error": "无法加载评测报告"}
        
        comparison = {
            "old_run_id": old_run_id,
            "new_run_id": new_run_id,
            "old_timestamp": old_report.get("timestamp", ""),
            "new_timestamp": new_report.get("timestamp", ""),
            "old_agent_version": old_report.get("agent_version", ""),
            "new_agent_version": new_report.get("agent_version", ""),
            
            # 总览对比
            "summary": {
                "old_pass_rate": old_report.get("pass_rate", 0),
                "new_pass_rate": new_report.get("pass_rate", 0),
                "pass_rate_change": new_report.get("pass_rate", 0) - old_report.get("pass_rate", 0),
                "old_total": old_report.get("total_cases", 0),
                "new_total": new_report.get("total_cases", 0),
            },
            
            # 分模块对比
            "by_module": {},
            
            # 用例级别变化
            "case_changes": {
                "fixed": [],      # 从失败变为通过
                "regressed": [],  # 从通过变为失败
                "new_failed": [], # 新增的失败用例
                "new_passed": [], # 新增的通过用例
            },
            
            # 性能对比
            "performance": {
                "old_p95_latency": old_report.get("p95_latency_ms", 0),
                "new_p95_latency": new_report.get("p95_latency_ms", 0),
            },
            
            # 红线对比
            "security": {
                "old_truthfulness_violations": old_report.get("truthfulness_violations", 0),
                "new_truthfulness_violations": new_report.get("truthfulness_violations", 0),
                "old_sensitive_data_leaks": old_report.get("sensitive_data_leaks", 0),
                "new_sensitive_data_leaks": new_report.get("sensitive_data_leaks", 0),
            }
        }
        
        # 分模块对比
        old_modules = old_report.get("by_module", {})
        new_modules = new_report.get("by_module", {})
        all_modules = set(list(old_modules.keys()) + list(new_modules.keys()))
        
        for module in all_modules:
            old_mr = old_modules.get(module, {})
            new_mr = new_modules.get(module, {})
            comparison["by_module"][module] = {
                "old_pass_rate": old_mr.get("pass_rate", 0),
                "new_pass_rate": new_mr.get("pass_rate", 0),
                "change": new_mr.get("pass_rate", 0) - old_mr.get("pass_rate", 0),
            }
        
        # 用例级别变化
        old_results = {r["case_id"]: r for r in old_report.get("case_results", [])}
        new_results = {r["case_id"]: r for r in new_report.get("case_results", [])}
        
        all_case_ids = set(list(old_results.keys()) + list(new_results.keys()))
        
        for case_id in all_case_ids:
            old_r = old_results.get(case_id)
            new_r = new_results.get(case_id)
            
            if old_r and new_r:
                old_passed = old_r.get("passed", False)
                new_passed = new_r.get("passed", False)
                
                if not old_passed and new_passed:
                    comparison["case_changes"]["fixed"].append(case_id)
                elif old_passed and not new_passed:
                    comparison["case_changes"]["regressed"].append(case_id)
            elif new_r and not old_r:
                if new_r.get("passed"):
                    comparison["case_changes"]["new_passed"].append(case_id)
                else:
                    comparison["case_changes"]["new_failed"].append(case_id)
        
        # 判断是否退化
        comparison["is_regression"] = (
            len(comparison["case_changes"]["regressed"]) > len(comparison["case_changes"]["fixed"])
            or comparison["summary"]["pass_rate_change"] < -0.05
        )
        
        return comparison
    
    def print_comparison(self, comparison: Dict[str, Any]):
        """打印版本对比报告"""
        lines = []
        lines.append("")
        lines.append("=" * 60)
        lines.append("  版本对比报告")
        lines.append(f"  旧版本: {comparison.get('old_run_id', 'N/A')} ({comparison.get('old_agent_version', '')})")
        lines.append(f"  新版本: {comparison.get('new_run_id', 'N/A')} ({comparison.get('new_agent_version', '')})")
        lines.append("=" * 60)
        
        summary = comparison.get("summary", {})
        change = summary.get("pass_rate_change", 0)
        icon = "📈" if change > 0 else "📉" if change < 0 else "➡️"
        
        lines.append("")
        lines.append(f"📊 总览 {icon}")
        lines.append(f"  旧版通过率: {summary.get('old_pass_rate', 0):.1%}")
        lines.append(f"  新版通过率: {summary.get('new_pass_rate', 0):.1%}")
        lines.append(f"  变化: {change:+.1%}")
        
        lines.append("")
        lines.append("📋 分模块对比")
        for module, data in comparison.get("by_module", {}).items():
            ch = data.get("change", 0)
            icon = "✅" if ch >= 0 else "❌"
            lines.append(f"  {module}: {data.get('old_pass_rate', 0):.0%} → {data.get('new_pass_rate', 0):.0%} ({ch:+.0%}) {icon}")
        
        changes = comparison.get("case_changes", {})
        lines.append("")
        lines.append("🔄 用例变化")
        lines.append(f"  修复: {len(changes.get('fixed', []))}条")
        for c in changes.get("fixed", []):
            lines.append(f"    ✅ {c}")
        lines.append(f"  退化: {len(changes.get('regressed', []))}条")
        for c in changes.get("regressed", []):
            lines.append(f"    ❌ {c}")
        
        regression = comparison.get("is_regression", False)
        lines.append("")
        lines.append(f"🚦 回归判断: {'❌ 检测到回归!' if regression else '✅ 无回归'}")
        
        lines.append("=" * 60)
        
        report_text = "\n".join(lines)
        logger.info(report_text)
        return report_text
    
    def _load_report(self, run_id: str) -> Optional[Dict]:
        """加载评测报告"""
        file_path = self.results_dir / f"{run_id}.json"
        if file_path.exists():
            with open(file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        logger.warning(f"评测报告不存在: {file_path}")
        return None


class EvalSetEvolver:
    """评测集演化器
    
    根据失败模式建议新增评测用例，持续完善评测集。
    """
    
    def __init__(self):
        self.suggestions: List[Dict] = []
    
    def analyze_failure_patterns(self, report: EvalReport) -> List[Dict]:
        """分析失败模式，生成评测集演化建议"""
        suggestions = []
        
        # 按模块统计失败
        module_failures: Dict[str, List[CaseResult]] = {}
        for r in report.case_results:
            if not r.passed:
                module = r.module
                if module not in module_failures:
                    module_failures[module] = []
                module_failures[module].append(r)
        
        # 分析每个模块的失败模式
        for module, failures in module_failures.items():
            # 统计失败标签
            tag_counts: Dict[str, int] = {}
            for f in failures:
                for tag in f.tags:
                    tag_counts[tag] = tag_counts.get(tag, 0) + 1
            
            # 高频失败标签
            for tag, count in tag_counts.items():
                if count >= 2:
                    suggestions.append({
                        "type": "new_case_suggestion",
                        "module": module,
                        "tag": tag,
                        "failure_count": count,
                        "reason": f"标签'{tag}'在{module}模块中有{count}条用例失败，建议增加该类型的覆盖",
                        "priority": "high" if any(f.priority == "P0" for f in failures) else "medium"
                    })
            
            # 红线违规
            red_line_failures = [f for f in failures if f.red_line_violations]
            if red_line_failures:
                suggestions.append({
                    "type": "red_line_alert",
                    "module": module,
                    "failure_count": len(red_line_failures),
                    "reason": f"{module}模块有{len(red_line_failures)}条红线违规，需要立即修复",
                    "priority": "critical"
                })
        
        # 性能退化建议
        slow_cases = [r for r in report.case_results if r.latency_ms > 15000]
        if slow_cases:
            suggestions.append({
                "type": "performance_alert",
                "failure_count": len(slow_cases),
                "reason": f"有{len(slow_cases)}条用例延迟超过15秒，需要性能优化",
                "priority": "high"
            })
        
        self.suggestions = suggestions
        return suggestions
    
    def generate_regression_cases(self, bad_cases: List[Dict]) -> List[EvalCase]:
        """根据bad case生成回归测试用例
        
        将历史失败用例转化为回归测试，确保修复后不再失败。
        """
        # 这里简化处理：直接记录bad case信息
        # 实际使用时可以将bad case转化为EvalCase格式
        logger.info(f"从 {len(bad_cases)} 条bad case中生成回归测试建议")
        return []
    
    def print_suggestions(self):
        """打印演化建议"""
        if not self.suggestions:
            logger.info("暂无评测集演化建议")
            return
        
        lines = []
        lines.append("")
        lines.append("📝 评测集演化建议")
        lines.append("-" * 40)
        
        for i, s in enumerate(self.suggestions, 1):
            priority_icon = {"critical": "🔴", "high": "🟠", "medium": "🟡"}.get(s.get("priority", ""), "⚪")
            lines.append(f"  {priority_icon} [{i}] {s['type']}: {s['reason']}")
        
        logger.info("\n".join(lines))


class FlywheelOrchestrator:
    """飞轮编排器
    
    整合所有飞轮组件，实现完整的评估驱动开发循环。
    """
    
    def __init__(self, results_dir: str = None):
        self.bad_case_collector = BadCaseCollector(results_dir)
        self.version_comparator = VersionComparator(results_dir)
        self.eval_set_evolver = EvalSetEvolver()
        self.results_dir = Path(results_dir or "./tests/eval/results")
    
    def run_eval_and_flywheel(self, report: EvalReport, 
                               compare_with: str = None) -> Dict[str, Any]:
        """运行评测并触发飞轮"""
        flywheel_result = {
            "run_id": report.run_id,
            "timestamp": datetime.now().isoformat(),
        }
        
        # Step 1: 收集bad case
        bad_cases = self.bad_case_collector.collect_from_report(report)
        flywheel_result["bad_cases_collected"] = len(bad_cases)
        
        # Step 2: 分析失败模式
        suggestions = self.eval_set_evolver.analyze_failure_patterns(report)
        flywheel_result["evolution_suggestions"] = len(suggestions)
        
        # Step 3: 版本对比（如果有对比版本）
        if compare_with:
            comparison = self.version_comparator.compare(compare_with, report.run_id)
            flywheel_result["version_comparison"] = comparison
            flywheel_result["is_regression"] = comparison.get("is_regression", False)
            self.version_comparator.print_comparison(comparison)
        
        # Step 4: 获取反复出现的bad case
        recurring = self.bad_case_collector.get_recurring_bad_cases()
        flywheel_result["recurring_bad_cases"] = len(recurring)
        
        # Step 5: 打印建议
        self.eval_set_evolver.print_suggestions()
        
        # Step 6: 保存飞轮报告
        flywheel_file = self.results_dir / f"flywheel_{report.run_id}.json"
        with open(flywheel_file, "w", encoding="utf-8") as f:
            json.dump(flywheel_result, f, ensure_ascii=False, indent=2, default=str)
        
        logger.info(f"飞轮报告已保存: {flywheel_file}")
        
        return flywheel_result
    
    def list_eval_runs(self) -> List[Dict]:
        """列出所有评测运行"""
        runs = []
        for file in sorted(self.results_dir.glob("run_*.json")):
            if "summary" in file.name or "bad_cases" in file.name or "flywheel" in file.name:
                continue
            with open(file, "r", encoding="utf-8") as f:
                data = json.load(f)
                runs.append({
                    "run_id": data.get("run_id", file.stem),
                    "timestamp": data.get("timestamp", ""),
                    "agent_version": data.get("agent_version", ""),
                    "total_cases": data.get("total_cases", 0),
                    "pass_rate": data.get("pass_rate", 0),
                    "gate_passed": data.get("gate_passed", False)
                })
        return runs


# ============================================================
# 线上 Bad Case 回流管道（SDD §5.6，M3）
# 12 类规则命中 requests.jsonl → 生成草稿 → 去重/severity 排序
# → pending_review.json；人工评审（合入/丢弃）后归档，不自动合入评测集（D7）
# ============================================================

_FLYWHEEL_ROOT = Path(__file__).resolve().parents[2]           # job-agent/
_OBS_DIR = _FLYWHEEL_ROOT / "data" / "observability"
_BAD_CASE_DIR = Path(__file__).resolve().parent / "results" / "bad_cases"

_SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}
_SEVERITY_TO_PRIORITY = {"critical": "P0", "high": "P1", "medium": "P2", "low": "P2"}
# intent → 评测模块（无 intent 时按层兜底）
_INTENT_TO_MODULE = {
    "resume_parse": "resume_parse", "parse_resume": "resume_parse",
    "jd_parse": "jd_parse", "parse_jd": "jd_parse",
    "job_score": "job_score", "jd_evaluate": "job_score", "score_job": "job_score",
    "resume_optimize": "resume_optimize", "optimize_resume": "resume_optimize",
    "interview": "interview", "interview_sim": "interview",
    "general_chat": "chat_engine",
}
_LAYER_TO_MODULE = {"L2": "env_degradation", "L4": "routing_layer",
                    "L5": "business_layer", "L6": "interaction", "security": "security_deep"}

# PII 脱敏扫描样式（合入前二次确认，SDD §5.10.3 pii_hits）
_PII_PATTERNS = {
    "phone": re.compile(r"1[3-9]\d{9}"),
    "email": re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+"),
    "id_card": re.compile(r"\d{17}[\dXx]"),
}


def _stream_of(r: Dict) -> Dict:
    return r.get("stream") or {}


def _scan_pii(text: str) -> List[str]:
    hits = []
    for name, pat in _PII_PATTERNS.items():
        if text and pat.search(text):
            hits.append(name)
    return hits


# 12 类规则（需求 6.2）：(规则名, 判据, severity, layer)
# 判据对 dict 记录安全取值；缺字段（M4/M6 未上线）自然不命中
RULES: List[Tuple[str, Callable[[Dict], bool], str, str]] = [
    ("slow", lambda r: (r.get("duration_ms") or 0) > 20000, "high", "L3"),
    ("slow_first_token", lambda r: (r.get("ttft_ms") or 0) > 5000, "high", "L3"),
    ("stream_degraded", lambda r: _stream_of(r).get("gap_median_ms") is not None
        and _stream_of(r).get("gap_median_ms") < 5
        and (_stream_of(r).get("delta_count") or 0) > 5, "critical", "L3"),
    ("error", lambda r: r.get("status") == "error", "critical", "L3"),
    ("user_impatient", lambda r: bool(r.get("user_interrupted"))
        and (r.get("waited_ms") or 0) > 3000, "high", "L3"),
    ("timeout", lambda r: r.get("status") == "timeout", "critical", "L3"),
    ("llm_degraded", lambda r: bool(r.get("degraded")), "critical", "L2"),
    ("low_confidence_intent", lambda r: (r.get("intent_confidence")
        if r.get("intent_confidence") is not None else 1) < 0.4, "medium", "L4"),
    ("quality_flagged", lambda r: bool(r.get("quality_low")) or bool(r.get("empty_reply")), "high", "L5"),
    ("security_hit", lambda r: bool(r.get("security_hit")), "critical", "security"),
    ("explicit_negative", lambda r: r.get("rating") == -1, "high", "L6"),
    ("rum_error", lambda r: bool(r.get("rum_error")), "medium", "L6"),
]


class ProductionBadCaseCollector:
    """线上流量 bad case 规则引擎 + 评审队列（SDD §5.6）

    - collect()：扫 requests.jsonl（并合并 quality/rum 派生字段）→ 命中规则生成草稿
      → 去重（rule + preview 前 50 字符）+ severity 排序 → 写当日快照 + pending_review.json
    - review()：合入（需 expected）/丢弃（需 reason）→ 更新状态 + 归档 processed
    - to_eval_case()：草稿 → EvalCase 就绪 dict（人工合入 eval_cases_v2.py 前的中间态）
    """

    def __init__(self, storage_dir: str = None):
        self.storage_dir = Path(storage_dir) if storage_dir else _BAD_CASE_DIR
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.pending_path = self.storage_dir / "pending_review.json"

    # ---------- 读取 ----------

    @staticmethod
    def _read_jsonl(path: Path) -> List[Dict]:
        if not path.exists():
            return []
        out = []
        try:
            for line in path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line:
                    try:
                        out.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass
        except Exception as e:
            logger.warning(f"读取观测数据失败(降级): {path.name}: {e}")
        return out

    def _load_records(self) -> List[Dict]:
        """requests.jsonl 记录 + 按 trace_id 合并 quality/rum 派生字段"""
        recs = self._read_jsonl(_OBS_DIR / "requests.jsonl")
        # quality.jsonl → quality_low/empty_reply/security_hit
        q_by_trace: Dict[str, Dict] = {}
        for q in self._read_jsonl(_OBS_DIR / "quality.jsonl"):
            tid = q.get("trace_id")
            if tid:
                q_by_trace[tid] = q
        # rum.jsonl → rating/rum_error
        rum_by_trace: Dict[str, Dict] = {}
        for e in self._read_jsonl(_OBS_DIR / "rum.jsonl"):
            tid = e.get("trace_id")
            if not tid:
                continue
            agg = rum_by_trace.setdefault(tid, {"rating": None, "rum_error": False})
            if e.get("type") == "feedback" and e.get("rating") is not None:
                agg["rating"] = e.get("rating")
            if e.get("type") in ("js_error", "card_render_fail"):
                agg["rum_error"] = True
        for r in recs:
            tid = r.get("trace_id")
            q = q_by_trace.get(tid, {})
            if q:
                scores = q.get("scores") or {}
                r["empty_reply"] = q.get("empty_reply", False)
                r["security_hit"] = q.get("red_line_hit", False)
                # 质量分低于 60 视为 quality_low
                vals = [v for v in scores.values() if isinstance(v, (int, float))]
                r["quality_low"] = bool(vals) and (min(vals) < 60)
            rum = rum_by_trace.get(tid, {})
            if rum:
                if rum.get("rating") is not None:
                    r["rating"] = rum["rating"]
                r["rum_error"] = rum.get("rum_error", False)
        return recs

    # ---------- 草稿生成 ----------

    @staticmethod
    def _draft_id(trace_id: str, rule: str) -> str:
        return "bc-" + hashlib.md5(f"{trace_id}:{rule}".encode("utf-8")).hexdigest()[:10]

    def _make_draft(self, rec: Dict, rule: str, severity: str, layer: str) -> Dict:
        trace_id = rec.get("trace_id", "")
        preview = (rec.get("message_preview") or "")[:100]
        intent = rec.get("intent") or ""
        module = _INTENT_TO_MODULE.get(intent) or _LAYER_TO_MODULE.get(layer, "chat_engine")
        stream = _stream_of(rec)
        return {
            "id": self._draft_id(trace_id, rule),
            "rule": rule,
            "severity": severity,
            "layer": layer,
            "trace_id": trace_id,
            "message_preview": preview,
            "ts": rec.get("ts", ""),
            "metrics": {
                "duration_ms": rec.get("duration_ms"),
                "ttft_ms": rec.get("ttft_ms"),
                "gap_median_ms": stream.get("gap_median_ms"),
            },
            "draft": {
                "input": preview,
                "module": module,
                "priority": _SEVERITY_TO_PRIORITY.get(severity, "P2"),
                "tags": ["origin:production", rule, f"layer:{layer}"],
                "expected": "",
            },
            "pii_hits": _scan_pii(preview),
            "status": "pending",
            "collected_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        }

    def collect(self) -> Dict[str, Any]:
        """扫描线上记录 → 生成/去重/排序草稿 → 落盘。返回采集统计。"""
        recs = self._load_records()
        drafts: List[Dict] = []
        rule_hits: Dict[str, int] = {}
        for rec in recs:
            for rule, pred, severity, layer in RULES:
                try:
                    hit = bool(pred(rec))
                except Exception:
                    hit = False
                if hit:
                    drafts.append(self._make_draft(rec, rule, severity, layer))
                    rule_hits[rule] = rule_hits.get(rule, 0) + 1

        deduped = self._dedup(drafts)
        deduped.sort(key=lambda d: (_SEVERITY_ORDER.get(d["severity"], 9), d["ts"]))

        # 当日原始快照（含重复，供审计）
        day_path = self.storage_dir / f"production_{time.strftime('%Y%m%d')}.json"
        self._write_json(day_path, drafts)
        # 合并进 pending 队列（按 id 去重，保留已评审状态）
        merged = self._merge_into_pending(deduped)
        logger.info(f"线上回流采集: 命中 {len(drafts)} 条草稿, 去重后 {len(deduped)} 条, "
                    f"队列新增 {merged['added']} 条")
        return {"raw_hits": len(drafts), "deduped": len(deduped),
                "rule_hits": rule_hits, "queue_added": merged["added"],
                "queue_pending": merged["pending"]}

    @staticmethod
    def _dedup(drafts: List[Dict]) -> List[Dict]:
        """去重键 = rule + preview 前 50 字符；保留最高 severity，累计 occurrences"""
        best: Dict[Tuple[str, str], Dict] = {}
        for d in drafts:
            key = (d["rule"], (d["message_preview"] or "")[:50])
            if key not in best:
                d = dict(d)
                d["occurrences"] = 1
                best[key] = d
            else:
                exist = best[key]
                exist["occurrences"] = exist.get("occurrences", 1) + 1
                if _SEVERITY_ORDER.get(d["severity"], 9) < _SEVERITY_ORDER.get(exist["severity"], 9):
                    exist["severity"] = d["severity"]
        return list(best.values())

    def _read_pending(self) -> List[Dict]:
        try:
            if self.pending_path.exists():
                return json.loads(self.pending_path.read_text(encoding="utf-8"))
        except Exception as e:
            logger.warning(f"读取评审队列失败(降级): {e}")
        return []

    @staticmethod
    def _write_json(path: Path, data: Any) -> None:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(data, ensure_ascii=False, indent=2, default=str),
                            encoding="utf-8")
        except Exception as e:
            logger.warning(f"写入 {path.name} 失败(降级): {e}")

    def _merge_into_pending(self, deduped: List[Dict]) -> Dict[str, int]:
        queue = self._read_pending()
        by_id = {q["id"]: q for q in queue}
        added = 0
        for d in deduped:
            if d["id"] in by_id:
                # 已存在：仅刷新计数/指标，不覆盖评审状态
                cur = by_id[d["id"]]
                cur["occurrences"] = max(cur.get("occurrences", 1), d.get("occurrences", 1))
                cur["last_seen_at"] = d["collected_at"]
            else:
                by_id[d["id"]] = d
                added += 1
        new_queue = list(by_id.values())
        new_queue.sort(key=lambda x: (_SEVERITY_ORDER.get(x["severity"], 9), x.get("ts", "")))
        self._write_json(self.pending_path, new_queue)
        pending = sum(1 for q in new_queue if q.get("status") == "pending")
        return {"added": added, "pending": pending}

    # ---------- 评审 ----------

    def get_queue(self, status: str = "pending") -> List[Dict]:
        queue = self._read_pending()
        if status and status != "all":
            queue = [q for q in queue if q.get("status") == status]
        return queue

    def to_eval_case(self, draft: Dict, expected: str = "") -> Dict[str, Any]:
        """草稿 → EvalCase 就绪 dict（人工合入 eval_cases_v2.py 前的中间态）"""
        d = draft.get("draft", {})
        case_id = f"PROD-{draft['id'].upper()}"
        return {
            "id": case_id,
            "module": d.get("module", "chat_engine"),
            "sub_type": draft.get("rule", ""),
            "priority": d.get("priority", "P2"),
            "risk_level": draft.get("severity", "medium"),
            "tags": d.get("tags", []),
            "input": {"user_message": d.get("input", "")},
            "expected": {"expected_behavior": expected or "（待人工补充期望）"},
            "eval": {"method": "human", "pass_criteria": expected or "人工评审"},
            "_meta": {"trace_id": draft.get("trace_id"), "rule": draft.get("rule"),
                      "pii_hits": draft.get("pii_hits", []),
                      "origin": "production", "collected_at": draft.get("collected_at")},
        }

    def review(self, draft_id: str, action: str, expected: str = "",
               reason: str = "") -> Dict[str, Any]:
        """评审：merge（需 expected）/discard（需 reason）→ 更新状态 + 归档 processed"""
        queue = self._read_pending()
        target = next((q for q in queue if q["id"] == draft_id), None)
        if not target:
            return {"ok": False, "error": f"草稿不存在: {draft_id}"}
        action = (action or "").lower()
        if action == "merge":
            if not (expected or "").strip():
                return {"ok": False, "error": "合入需填写 expected（D7：期望值须人判断）"}
            target["status"] = "merged"
            target["expected"] = expected
            eval_case = self.to_eval_case(target, expected)
        elif action == "discard":
            if not (reason or "").strip():
                return {"ok": False, "error": "丢弃需填写 reason"}
            target["status"] = "discarded"
            target["discard_reason"] = reason
            eval_case = None
        else:
            return {"ok": False, "error": f"未知 action: {action}（应为 merge/discard）"}

        target["reviewed_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
        self._write_json(self.pending_path, queue)
        # 归档 processed（审计留痕）
        proc_path = self.storage_dir / f"processed_{time.strftime('%Y%m')}.json"
        proc = []
        try:
            if proc_path.exists():
                proc = json.loads(proc_path.read_text(encoding="utf-8"))
        except Exception:
            proc = []
        proc.append(target)
        self._write_json(proc_path, proc)
        # 合入的 eval case 单独落一份，供人工搬运到 eval_cases_v2.py
        merged_out = None
        if eval_case is not None:
            merged_path = self.storage_dir / "merged_eval_cases.json"
            merged = []
            try:
                if merged_path.exists():
                    merged = json.loads(merged_path.read_text(encoding="utf-8"))
            except Exception:
                merged = []
            merged = [m for m in merged if m.get("id") != eval_case["id"]]
            merged.append(eval_case)
            self._write_json(merged_path, merged)
            merged_out = eval_case
        return {"ok": True, "status": target["status"], "eval_case": merged_out}


def run_production_collection() -> Dict[str, Any]:
    """CLI 入口：跑一次线上回流采集"""
    return ProductionBadCaseCollector().collect()


# ============================================================
# 标准层能力（SDD §5.8，M5）
# 版本对比（US-S1）/ eval_set_hash（US-S2）/ 元评测（US-S3）
# / flake（US-S4）/ 周报（US-S5）
# ============================================================

_RESULTS_DIR = Path(__file__).resolve().parent / "results"


def _write_json_safe(path: Path, data: Any) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2, default=str),
                        encoding="utf-8")
    except Exception as e:
        logger.warning(f"写入 {path.name} 失败(降级): {e}")


def _iter_jsonl(path: Path):
    if not path.exists():
        return
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                pass
    except Exception:
        pass


def _count_by(items: List[Dict], key: str) -> Dict[str, int]:
    out: Dict[str, int] = {}
    for it in items:
        k = it.get(key, "?")
        out[k] = out.get(k, 0) + 1
    return out


def compute_eval_set_hash(cases) -> str:
    """评测集内容 hash（US-S2），委托 trace.py 统一实现"""
    from .trace import compute_eval_set_hash as _h
    return _h(cases)


def list_run_ids(results_dir: Path = None) -> List[str]:
    """按时间序列出评测 run_id（排除 summary/bad_cases/flywheel 派生文件）"""
    rd = Path(results_dir) if results_dir else _RESULTS_DIR
    ids = []
    for f in sorted(rd.glob("run_*.json")):
        if any(x in f.name for x in ("summary", "bad_cases", "flywheel")):
            continue
        ids.append(f.stem)
    return ids


def auto_compare_latest(new_run_id: str, results_dir: Path = None) -> Dict[str, Any]:
    """US-S1：每次评测自动与上一版本对比，回归即置 regression_alert。"""
    rd = Path(results_dir) if results_dir else _RESULTS_DIR
    prev = [r for r in list_run_ids(rd) if r != new_run_id]
    if not prev:
        return {"compared": False, "reason": "无历史版本可对比"}
    old = prev[-1]
    comp = VersionComparator(str(rd)).compare(old, new_run_id)
    comp["compared"] = not comp.get("error")
    comp["regression_alert"] = bool(comp.get("is_regression", False))
    return comp


def run_meta_eval(month: str = None, sample_n: int = 20) -> Dict[str, Any]:
    """US-S3：月度从 judge_call.raw_reason 抽样 → meta_eval_YYYYMM.json。

    human_label 留空待人工标注；一致率 < 80% 触发 judge 修正（人工填 agreement_rate）。
    """
    import random
    month = month or time.strftime("%Y%m")
    traces_dir = _RESULTS_DIR / "eval_traces"
    reasons: List[Dict] = []
    if traces_dir.exists():
        for f in sorted(traces_dir.glob("*.jsonl")):
            for rec in _iter_jsonl(f):
                if rec.get("span") != "judge_call":
                    continue
                a = rec.get("attrs", {}) or {}
                if a.get("raw_reason"):
                    reasons.append({"run_id": rec.get("run_id"),
                                    "judge_type": a.get("judge_type"),
                                    "score": a.get("score"),
                                    "red_line": a.get("red_line"),
                                    "raw_reason": a.get("raw_reason")})
    sample = random.sample(reasons, min(sample_n, len(reasons))) if reasons else []
    out = {"month": month, "total_judge_calls": len(reasons), "sampled": len(sample),
           "agreement_rate": None, "needs_correction": None,
           "samples": [{**s, "human_label": None} for s in sample],
           "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S")}
    _write_json_safe(_RESULTS_DIR / f"meta_eval_{month}.json", out)
    return out


def detect_flake(reports: List[Dict], min_runs: int = 2) -> Dict[str, Any]:
    """US-S4：同一用例连跑 n 次通过结果不一致 → flake，不参与门禁。

    reports：多次运行的 report dict 列表（含 case_results）→ flake_cases.json。
    """
    passes: Dict[str, List[bool]] = {}
    for rep in reports:
        for r in rep.get("case_results", []):
            passes.setdefault(r.get("case_id"), []).append(bool(r.get("passed")))
    flake = []
    for cid, ps in passes.items():
        if cid and len(ps) >= min_runs and len(set(ps)) > 1:
            flake.append({"case_id": cid, "runs": len(ps), "pass_count": sum(ps),
                          "pass_rate": round(sum(ps) / len(ps), 3)})
    flake.sort(key=lambda x: x["pass_rate"])
    out = {"flake_cases": flake, "count": len(flake), "runs_analyzed": len(reports),
           "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S")}
    _write_json_safe(_RESULTS_DIR / "flake_cases.json", out)
    return out


def detect_flake_from_runs(run_ids: List[str], results_dir: Path = None) -> Dict[str, Any]:
    """从已落盘的多个 run 报告做 flake 检测（无需重跑）"""
    rd = Path(results_dir) if results_dir else _RESULTS_DIR
    reports = []
    for rid in run_ids:
        p = rd / f"{rid}.json"
        if p.exists():
            try:
                reports.append(json.loads(p.read_text(encoding="utf-8")))
            except Exception:
                pass
    return detect_flake(reports)


def generate_weekly_report(week: str = None) -> Dict[str, Any]:
    """US-S5：飞轮周报 = 评测运行 + 线上回流统计 → flywheel_weekly_YYYYWW.json"""
    week = week or time.strftime("%Y%W")
    orch = FlywheelOrchestrator(str(_RESULTS_DIR))
    runs = orch.list_eval_runs()
    collector = ProductionBadCaseCollector()
    pending = collector.get_queue("pending")
    merged = collector.get_queue("merged")
    discarded = collector.get_queue("discarded")
    out = {
        "week": week,
        "eval_runs": len(runs),
        "latest_run": runs[-1] if runs else None,
        "latest_pass_rate": runs[-1]["pass_rate"] if runs else None,
        "badcase_pending": len(pending),
        "badcase_merged": len(merged),
        "badcase_discarded": len(discarded),
        "pending_by_severity": _count_by(pending, "severity"),
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    _write_json_safe(_RESULTS_DIR / f"flywheel_weekly_{week}.json", out)
    return out


def read_weekly_report(week: str = None) -> Dict[str, Any]:
    """读已生成周报；缺失时即时生成（API /weekly 用）"""
    week = week or time.strftime("%Y%W")
    path = _RESULTS_DIR / f"flywheel_weekly_{week}.json"
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            pass
    return generate_weekly_report(week)


if __name__ == "__main__":
    import sys
    cmd = sys.argv[1] if len(sys.argv) > 1 else "collect"
    if cmd == "collect":
        stats = run_production_collection()
        print(json.dumps(stats, ensure_ascii=False, indent=2))
    elif cmd == "weekly":
        print(json.dumps(generate_weekly_report(), ensure_ascii=False, indent=2))
    elif cmd == "meta_eval":
        print(json.dumps(run_meta_eval(), ensure_ascii=False, indent=2))
    elif cmd == "compare" and len(sys.argv) > 2:
        print(json.dumps(auto_compare_latest(sys.argv[2]), ensure_ascii=False, indent=2))
    else:
        print("用法: python tests/eval/flywheel.py [collect|weekly|meta_eval|compare <new_run_id>]")
