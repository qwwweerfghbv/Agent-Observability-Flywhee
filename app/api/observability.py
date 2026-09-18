"""可观测平台聚合 API（SDD §6.1）

M3：线上 bad case 评审队列
M5：总览/链路/指标/SLO/变更/质量/报告中心/评测链路/周报 聚合端点

UI 一律经此取数，不直接解析 JSONL（D9/US-U3）：读接口离线聚合
data/observability/*.jsonl 与 tests/eval/results/*，复用 monitor.py 聚合/SLO 判定。
"""
from typing import Any, Dict, List, Optional

from fastapi import APIRouter
from loguru import logger
from pydantic import BaseModel

router = APIRouter(prefix="/api/observability", tags=["可观测"])


def _collector():
    """延迟导入线上回流采集器（避免 app 启动即拉起 tests.eval 依赖）"""
    from tests.eval.flywheel import ProductionBadCaseCollector
    return ProductionBadCaseCollector()


class ReviewRequest(BaseModel):
    action: str                       # merge | discard
    expected: Optional[str] = ""      # merge 时必填（期望行为，D7 人工判断）
    reason: Optional[str] = ""        # discard 时必填


@router.get("/badcases")
async def list_badcases(status: str = "pending", refresh: bool = False) -> Dict[str, Any]:
    """评审队列。refresh=true 先跑一次线上回流采集再返回。"""
    try:
        collector = _collector()
        stats = collector.collect() if refresh else None
        items: List[Dict] = collector.get_queue(status=status)
        by_severity: Dict[str, int] = {}
        for it in items:
            by_severity[it.get("severity", "?")] = by_severity.get(it.get("severity", "?"), 0) + 1
        return {"status": status, "count": len(items),
                "by_severity": by_severity, "items": items,
                "collect_stats": stats}
    except Exception as e:
        logger.error(f"读取评审队列失败: {e}")
        return {"status": status, "count": 0, "by_severity": {}, "items": [], "error": str(e)}


@router.post("/badcases/{draft_id}/review")
async def review_badcase(draft_id: str, req: ReviewRequest) -> Dict[str, Any]:
    """评审单条草稿：merge（需 expected）/ discard（需 reason）→ 更新状态 + 归档"""
    try:
        result = _collector().review(
            draft_id, req.action, expected=req.expected or "", reason=req.reason or "")
        return result
    except Exception as e:
        logger.error(f"评审 bad case 失败: {e}")
        return {"ok": False, "error": str(e)}


# ============================================================
# M5 聚合端点（SDD §6.1）——复用 tests/eval/monitor.py 聚合与 SLO 判定
# ============================================================

def _monitor():
    from tests.eval import monitor
    return monitor


def _obs_dir():
    from app.observability.writers import OBS_DIR
    return OBS_DIR


def _read_jsonl(path):
    return _monitor()._read_jsonl(path)


def _health_score(slo: List[Dict]) -> int:
    """健康分：满分 100，critical -15 / warning -5，下限 0"""
    score = 100
    for s in slo:
        st = s.get("state")
        if st == "critical":
            score -= 15
        elif st == "warning":
            score -= 5
    return max(0, score)


def _slo_light(slo: List[Dict], metric: str, default: str = "green") -> str:
    """按 SLO 判定结果映射七层灯色"""
    m = {"ok": "green", "no_data": "unknown", "warning": "warning", "critical": "critical"}
    for s in slo:
        if s.get("metric") == metric:
            return m.get(s.get("state"), default)
    return default


@router.get("/summary")
async def get_summary(window: str = "24h") -> Dict[str, Any]:
    """总览：健康分 + 七层状态灯 + 飞轮四环节计数 + 告警清单（US-U3）"""
    try:
        m = _monitor()
        recs = m.load_window(window, "production")
        agg = m.aggregate(recs)
        infra = m.latest_infra()
        slo = m.judge_slo(agg, infra)
        n = agg.get("request_count", 0)

        amb = sum(1 for r in recs if r.get("ambiguous"))
        empty = sum(1 for r in recs if r.get("empty_reply"))
        sec = sum(1 for r in recs if r.get("security_hit"))
        # 告警收敛（SDD §5.9）：打扰型 critical（注入命中/记忆异常）仅统计最近 1h，
        # 同类 1h 未复现即收敛，侧栏红点/桌面 toast 自然消失；
        # 层状态灯仍按所选窗口展示（页面分析视图，非打扰通道）
        recs_1h = m.load_window("1h", "production")
        agg_1h = m.aggregate(recs_1h)
        sec_1h = sum(1 for r in recs_1h if r.get("security_hit"))
        mem_crit_1h = agg_1h.get("memory_error_count", 0) or 0
        mem_warn_1h = agg_1h.get("memory_warn_count", 0) or 0
        mem_flag_dist_1h = agg_1h.get("memory_flag_dist") or {}
        # 记忆观测（L4）：flag 聚合 + 长期记忆存储探针
        mem_crit = agg.get("memory_error_count", 0) or 0
        mem_warn = agg.get("memory_warn_count", 0) or 0
        mem_flag_dist = agg.get("memory_flag_dist") or {}
        try:
            from app.observability.memory_guard import probe_long_term_storage
            lt_probe = probe_long_term_storage()
        except Exception as e:
            lt_probe = {"status": "unknown", "errors": [str(e)]}
        mem_status = "green"
        if mem_warn:
            mem_status = "warning"
        if mem_crit or lt_probe.get("status") == "critical":
            mem_status = "critical"
        qvals: List[float] = []
        for rec in _read_jsonl(_obs_dir() / "quality.jsonl"):
            for v in (rec.get("scores") or {}).values():
                if isinstance(v, (int, float)):
                    qvals.append(v)
        quality_avg = round(sum(qvals) / len(qvals) / 100, 3) if qvals else None
        intent_dist = agg.get("intent_dist") or {}
        top_intent = max(intent_dist, key=intent_dist.get) if intent_dist else None

        layers = {
            "L1": {"status": _slo_light(slo, "disk_free_gb"),
                   "disk_free_gb": infra.get("C_free_gb")},
            "L2": {"status": _slo_light(slo, "llm_error_rate"),
                   "degraded": agg.get("degraded_count", 0),
                   "llm_error_rate": agg.get("llm_error_rate")},
            "L3": {"status": _slo_light(slo, "ttft_p95_ms"),
                   "ttft_p95_ms": agg.get("ttft_p95_ms"),
                   "error_rate": agg.get("request_error_rate"),
                   "interrupt_rate": agg.get("interrupted_rate")},
            "L4": {"status": "critical" if (sec or mem_status == "critical")
                   else ("warning" if mem_status == "warning" else "green"),
                   "low_conf_intent_rate": round(amb / n, 4) if n else None,
                   "security_hit": sec,
                   "memory_status": mem_status,
                   "memory_errors": mem_crit,
                   "memory_warns": mem_warn,
                   "memory_flag_dist": mem_flag_dist,
                   "long_term_storage": lt_probe.get("status")},
            "L5": {"status": "green", "quality_avg": quality_avg,
                   "empty_reply_rate": round(empty / n, 4) if n else None},
            "L6": {"status": "unknown", "note": "M6 未上线"},
            "L7": {"status": "green", "top_intent": top_intent},
        }
        alerts = [{"level": s.get("level", "warning"), "layer": s.get("layer"),
                   "rule": s.get("metric"),
                   "msg": f"{s.get('metric')}={s.get('actual')} 违反 {s.get('op')} {s.get('value')}"}
                  for s in slo if s.get("state") in ("warning", "critical")]
        if sec_1h:
            alerts.append({"level": "critical", "layer": "L4", "rule": "security_hit",
                           "msg": f"近1h {sec_1h} 次注入/敏感信息命中（同类1h未复现即收敛）"})
        if mem_crit_1h:
            alerts.append({"level": "critical", "layer": "L4", "rule": "memory_error",
                           "msg": f"近1h {mem_crit_1h} 次严重记忆异常"
                                  f"(会话持久化/长期IO): {sorted(mem_flag_dist_1h)}，"
                                  f"同类1h未复现即收敛"})
        elif mem_warn_1h:
            alerts.append({"level": "warning", "layer": "L4", "rule": "memory_warn",
                           "msg": f"近1h {mem_warn_1h} 次警告级记忆异常"
                                  f"(压缩频繁/上下文未注入): {sorted(mem_flag_dist_1h)}"})
        if lt_probe.get("errors"):
            alerts.append({"level": "critical", "layer": "L4", "rule": "long_term_storage",
                           "msg": f"长期记忆存储探针失败: {lt_probe['errors']}"})

        collector = _collector()
        pending = collector.get_queue("pending")
        merged = collector.get_queue("merged")
        return {
            "health_score": _health_score(slo),
            "window": window,
            "request_count": n,
            "layers": layers,
            "flywheel": {"badcase_pending": len(pending),
                         "merged_this_week": len(merged),
                         "prod_case_pass_rate": None},
            "alerts": alerts,
        }
    except Exception as e:
        logger.error(f"总览聚合失败: {e}")
        return {"window": window, "error": str(e), "layers": {}, "alerts": []}


@router.get("/metrics")
async def get_metrics(window: str = "1h") -> Dict[str, Any]:
    """分层指标窗口聚合（直接复用 monitor.aggregate）"""
    try:
        m = _monitor()
        recs = m.load_window(window, "production")
        return {"window": window, "aggregate": m.aggregate(recs),
                "infra_latest": m.latest_infra()}
    except Exception as e:
        logger.error(f"指标聚合失败: {e}")
        return {"window": window, "error": str(e)}


@router.get("/slo")
async def get_slo(window: str = "24h") -> Dict[str, Any]:
    """分层 SLO 红绿灯 + 违规清单"""
    try:
        m = _monitor()
        recs = m.load_window(window, "production")
        agg = m.aggregate(recs)
        slo = m.judge_slo(agg, m.latest_infra())
        return {"window": window, "slo": slo,
                "critical_violations": [s for s in slo if s.get("state") == "critical"],
                "warning_violations": [s for s in slo if s.get("state") == "warning"],
                "health_score": _health_score(slo)}
    except Exception as e:
        logger.error(f"SLO 判定失败: {e}")
        return {"window": window, "error": str(e), "slo": []}


def _trace_item(r: Dict) -> Dict[str, Any]:
    return {"trace_id": r.get("trace_id"), "ts": r.get("ts"), "path": r.get("path"),
            "method": r.get("method"), "intent": r.get("intent"),
            "status": r.get("status"), "duration_ms": r.get("duration_ms"),
            "ttft_ms": r.get("ttft_ms"), "degraded": bool(r.get("degraded")),
            "user_interrupted": bool(r.get("user_interrupted")),
            "security_hit": bool(r.get("security_hit")),
            "message_preview": r.get("message_preview")}


@router.get("/traces")
async def list_traces(window: str = "24h", trace_id: Optional[str] = None,
                      path: Optional[str] = None, intent: Optional[str] = None,
                      status: Optional[str] = None, level: Optional[str] = None,
                      limit: int = 50) -> Dict[str, Any]:
    """链路检索（分页 + 过滤）"""
    try:
        m = _monitor()
        recs = m.load_window(window, None)
        if trace_id:
            recs = [r for r in recs if r.get("trace_id") == trace_id]
        if path:
            recs = [r for r in recs if path in (r.get("path") or "")]
        if intent:
            recs = [r for r in recs if r.get("intent") == intent]
        if status:
            recs = [r for r in recs if r.get("status") == status]
        if level == "critical":
            recs = [r for r in recs if r.get("security_hit") or r.get("status") == "error"]
        recs = sorted(recs, key=lambda r: r.get("ts") or "", reverse=True)
        items = [_trace_item(r) for r in recs[:limit]]
        return {"window": window, "count": len(recs), "returned": len(items), "items": items}
    except Exception as e:
        logger.error(f"链路检索失败: {e}")
        return {"window": window, "count": 0, "items": [], "error": str(e)}


@router.get("/traces/{trace_id}")
async def get_trace_detail(trace_id: str) -> Dict[str, Any]:
    """单链路耗时分解 + 关联日志（spans）（US-O3）"""
    try:
        m = _monitor()
        rec = next((r for r in m._read_jsonl(m.REQUESTS_PATH)
                    if r.get("trace_id") == trace_id), None)
        if not rec:
            return {"trace_id": trace_id, "error": "trace 不存在"}
        stream = rec.get("stream") or {}
        ttft = rec.get("ttft_ms")
        first_delta = rec.get("llm_first_delta_ms")
        preprocess = round(ttft - first_delta, 1) if (ttft is not None and first_delta is not None) else None
        spans = rec.get("spans") or []
        logs = [f"{s.get('ts')} | {s.get('span')} | " +
                ", ".join(f"{k}={v}" for k, v in s.items() if k not in ("span", "ts"))
                for s in spans]
        # 关联质量哨兵评分（quality.jsonl 同 trace 的 scored 记录）→ 单条 trace 可见内容质量
        qrec = next((r for r in reversed(_read_jsonl(_obs_dir() / "quality.jsonl"))
                     if r.get("trace_id") == trace_id and r.get("sampled") and r.get("scores")), None)
        return {
            "trace_id": trace_id, "path": rec.get("path"), "method": rec.get("method"),
            "status": rec.get("status"), "ts": rec.get("ts"),
            "timing": {"preprocess_ms": preprocess, "ttft_ms": ttft,
                       "stream_span_ms": stream.get("total_span_ms"),
                       "llm_duration_ms": rec.get("llm_duration_ms"),
                       "total_ms": rec.get("duration_ms")},
            "stream": {"delta_count": stream.get("delta_count"),
                       "gap_median_ms": stream.get("gap_median_ms")},
            "intent": {"name": rec.get("intent"), "confidence": rec.get("intent_confidence"),
                       "ambiguous": rec.get("ambiguous"), "router": rec.get("intent_router"),
                       "clarified": rec.get("clarified")},
            "llm": {"model": rec.get("model"), "tokens": rec.get("tokens"),
                    "degraded": bool(rec.get("degraded")), "llm_error": rec.get("llm_error")},
            "quality": {"card_count": rec.get("card_count"), "empty_reply": rec.get("empty_reply"),
                        "security_hit": rec.get("security_hit"), "quality_flags": rec.get("quality_flags"),
                        "scores": (qrec or {}).get("scores"),
                        "judge_reason": (qrec or {}).get("judge_reason"),
                        "judge_model": (qrec or {}).get("judge_model")},
            "memory": {"flags": rec.get("memory_flags"),
                       "msg_persisted": rec.get("msg_persisted"),
                       "spans": [s for s in spans if s.get("span") == "memory"]},
            "version": rec.get("version"),
            "spans": spans, "logs": logs,
        }
    except Exception as e:
        logger.error(f"链路详情失败: {e}")
        return {"trace_id": trace_id, "error": str(e)}


@router.get("/events")
async def list_events(limit: int = 100) -> Dict[str, Any]:
    """变更标注时间线（events.jsonl，SDD §4.8）"""
    try:
        events = _read_jsonl(_obs_dir() / "events.jsonl")
        events = sorted(events, key=lambda e: e.get("ts") or "", reverse=True)[:limit]
        return {"count": len(events), "items": events}
    except Exception as e:
        logger.error(f"读取变更事件失败: {e}")
        return {"count": 0, "items": [], "error": str(e)}


@router.get("/quality")
async def get_quality(window: str = "7d") -> Dict[str, Any]:
    """抽样质量分 + 幻觉/红线命中 + 质量标志分布"""
    try:
        recs = _read_jsonl(_obs_dir() / "quality.jsonl")
        scored = [r for r in recs if r.get("sampled") and r.get("scores")]
        red = sum(1 for r in recs if r.get("red_line_hit"))
        inj = sum(1 for r in recs if r.get("injection_hit"))
        sens = sum(1 for r in recs if r.get("sensitive_types"))
        flags: Dict[str, int] = {}
        for r in recs:
            for f in (r.get("quality_flags") or []):
                flags[f] = flags.get(f, 0) + 1
        dim_avg: Dict[str, float] = {}
        for r in scored:
            for k, v in (r.get("scores") or {}).items():
                if isinstance(v, (int, float)):
                    dim_avg.setdefault(k, []).append(v)
        dim_avg = {k: round(sum(v) / len(v), 1) for k, v in dim_avg.items() if v}
        return {"window": window, "total_records": len(recs), "sampled_scored": len(scored),
                "red_line_hits": red, "injection_hits": inj, "sensitive_hits": sens,
                "flag_dist": flags, "dimension_avg": dim_avg}
    except Exception as e:
        logger.error(f"质量聚合失败: {e}")
        return {"window": window, "error": str(e)}


@router.get("/reports")
async def get_reports(limit: int = 20) -> Dict[str, Any]:
    """评测报告中心：运行列表 + 最新版本对比 + flake 用例（US-S1/S4/S6）"""
    try:
        from tests.eval.flywheel import (FlywheelOrchestrator, auto_compare_latest,
                                         list_run_ids)
        orch = FlywheelOrchestrator()
        runs = orch.list_eval_runs()
        runs_desc = list(reversed(runs))[:limit]
        comparison = auto_compare_latest(runs[-1]["run_id"]) if runs else None
        flake = None
        fp = _monitor().RESULTS_DIR / "flake_cases.json"
        if fp.exists():
            import json as _json
            try:
                flake = _json.loads(fp.read_text(encoding="utf-8"))
            except Exception:
                flake = None
        return {"count": len(runs_desc), "runs": runs_desc,
                "latest_comparison": comparison, "flake": flake,
                "run_ids": list_run_ids()}
    except Exception as e:
        logger.error(f"报告中心聚合失败: {e}")
        return {"count": 0, "runs": [], "error": str(e)}


@router.get("/eval-traces/{run_id}")
async def get_eval_trace(run_id: str, tail: bool = False) -> Dict[str, Any]:
    """评测链路 span 树 + live 进度（US-S6/S7）"""
    try:
        from tests.eval.trace import read_eval_trace
        return read_eval_trace(run_id, tail=tail)
    except Exception as e:
        logger.error(f"读取评测链路失败: {e}")
        return {"run_id": run_id, "error": str(e), "spans": []}


@router.get("/weekly")
async def get_weekly(week: Optional[str] = None) -> Dict[str, Any]:
    """飞轮周报（US-S5）"""
    try:
        from tests.eval.flywheel import read_weekly_report
        return read_weekly_report(week)
    except Exception as e:
        logger.error(f"周报生成失败: {e}")
        return {"error": str(e)}


@router.post("/rum")
async def ingest_rum(event: Dict[str, Any]) -> Dict[str, Any]:
    """L6 RUM 上报采集入口（SDD §6.1/§4.7，M6）：js_error/card_render_fail/feedback 等。

    静默落 rum.jsonl；隐私约束（不含 DOM/消息全文）由前端上报侧保证。
    """
    try:
        from app.observability.writers import write_rum
        if not isinstance(event, dict) or not event.get("type"):
            return {"ok": False, "error": "body 须为含 type 的 JSON 对象"}
        write_rum(event)
        return {"ok": True, "type": event.get("type")}
    except Exception as e:
        logger.error(f"RUM 上报失败: {e}")
        return {"ok": False, "error": str(e)}
