"""运行监控：窗口聚合 + 分层 SLO 判定（SDD §5.5，M2）

读 data/observability/requests.jsonl 指定窗口的线上记录 → 分层聚合 →
逐条对照 tests/eval/slo_config.json 判定红绿灯 → 输出 results/monitor_YYYYMMDD.json
+ 终端摘要。退出码非零 ⟺ 存在 critical 违规。

用法：
    python tests/eval/monitor.py                 # 默认 24h 窗口
    python tests/eval/monitor.py --window 1h
    python tests/eval/monitor.py --window 7d --source production
"""
import argparse
import json
import os
import statistics
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

_JOB_AGENT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _JOB_AGENT_ROOT not in sys.path:
    sys.path.insert(0, _JOB_AGENT_ROOT)

from app.observability.writers import OBS_DIR  # noqa: E402
from app.observability.memory_guard import CRITICAL_MEMORY_FLAGS  # noqa: E402

REQUESTS_PATH = OBS_DIR / "requests.jsonl"
INFRA_PATH = OBS_DIR / "infra.jsonl"
SLO_CONFIG = Path(__file__).resolve().parent / "slo_config.json"
RESULTS_DIR = Path(__file__).resolve().parent / "results"

_WINDOWS = {"1h": timedelta(hours=1), "24h": timedelta(hours=24),
            "7d": timedelta(days=7), "30d": timedelta(days=30)}


def _parse_ts(ts: str):
    """解析 '2026-09-11T11:30:00.123' / '...T11:30:00'"""
    if not ts:
        return None
    try:
        return datetime.strptime(ts, "%Y-%m-%dT%H:%M:%S.%f")
    except ValueError:
        try:
            return datetime.strptime(ts, "%Y-%m-%dT%H:%M:%S")
        except ValueError:
            return None


def _read_jsonl(path: Path) -> list:
    if not path.exists():
        return []
    out = []
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    except Exception:
        pass
    return out


def load_window(window: str, source: str) -> list:
    """按时间窗 + source 过滤 requests.jsonl"""
    delta = _WINDOWS.get(window, timedelta(hours=24))
    cutoff = datetime.now() - delta
    recs = []
    for r in _read_jsonl(REQUESTS_PATH):
        if source and r.get("source", "production") != source:
            continue
        ts = _parse_ts(r.get("ts"))
        if ts is None or ts >= cutoff:
            recs.append(r)  # ts 缺失时保守纳入
    return recs


def _pct(vals, p):
    """百分位（nearest-rank）；空列表返回 None"""
    vals = [v for v in vals if v is not None]
    if not vals:
        return None
    s = sorted(vals)
    k = max(0, min(len(s) - 1, int(round(p / 100 * (len(s) - 1)))))
    return round(s[k], 1)


def _rate(num, den):
    return round(num / den, 4) if den else None


def aggregate(recs: list) -> dict:
    """分层聚合：请求量/状态分布/P50-P95/流式节奏/token/意图/模型/记忆异常"""
    n = len(recs)
    status_dist, intent_dist, model_dist = {}, {}, {}
    ttft, duration, gaps = [], [], []
    tokens_total = 0
    err_cnt = degraded_cnt = interrupted_cnt = llm_err_cnt = llm_call_cnt = 0
    mem_err_cnt = mem_warn_cnt = persist_fail_cnt = trim_event_cnt = 0
    memory_flag_dist = {}

    for r in recs:
        st = r.get("status", "ok")
        status_dist[st] = status_dist.get(st, 0) + 1
        code = r.get("status_code", 200) or 200
        if st == "error" or code >= 500:
            err_cnt += 1
        if r.get("degraded"):
            degraded_cnt += 1
        if r.get("user_interrupted"):
            interrupted_cnt += 1
        if r.get("llm_error"):
            llm_err_cnt += 1
        if (r.get("llm_calls") or 0) > 0:
            llm_call_cnt += 1
        if r.get("ttft_ms") is not None:
            ttft.append(r["ttft_ms"])
        if r.get("duration_ms") is not None:
            duration.append(r["duration_ms"])
        stream = r.get("stream") or {}
        if stream.get("gap_median_ms") is not None and stream.get("delta_count", 0) > 1:
            gaps.append(stream["gap_median_ms"])
        tk = r.get("tokens") or {}
        tokens_total += tk.get("total", 0) or 0
        if r.get("intent"):
            intent_dist[r["intent"]] = intent_dist.get(r["intent"], 0) + 1
        if r.get("model"):
            model_dist[r["model"]] = model_dist.get(r["model"], 0) + 1
        # 记忆异常聚合（memory_guard flag/span）
        flags = r.get("memory_flags") or []
        for f in flags:
            memory_flag_dist[f] = memory_flag_dist.get(f, 0) + 1
        if any(f in CRITICAL_MEMORY_FLAGS for f in flags):
            mem_err_cnt += 1
        elif flags:
            mem_warn_cnt += 1
        if r.get("msg_persisted") is False:
            persist_fail_cnt += 1
        for sp in (r.get("spans") or []):
            if sp.get("span") == "memory" and sp.get("op") == "trim":
                trim_event_cnt += 1

    return {
        "request_count": n,
        "status_dist": status_dist,
        "intent_dist": intent_dist,
        "model_dist": model_dist,
        "request_error_rate": _rate(err_cnt, n),
        "degraded_rate": _rate(degraded_cnt, n),
        "interrupted_rate": _rate(interrupted_cnt, n),
        "llm_error_rate": _rate(llm_err_cnt, llm_call_cnt),
        "error_count": err_cnt,
        "degraded_count": degraded_cnt,
        "interrupted_count": interrupted_cnt,
        "ttft_p50_ms": _pct(ttft, 50),
        "ttft_p95_ms": _pct(ttft, 95),
        "duration_p50_ms": _pct(duration, 50),
        "duration_p95_ms": _pct(duration, 95),
        "stream_gap_median_ms": round(statistics.median(gaps), 1) if gaps else None,
        "tokens_total": tokens_total,
        # 记忆观测指标（短期trim/中期持久化/长期IO）
        "memory_error_count": mem_err_cnt,
        "memory_warn_count": mem_warn_cnt,
        "memory_error_rate": _rate(mem_err_cnt, n),
        "memory_warn_rate": _rate(mem_warn_cnt, n),
        "memory_flag_dist": memory_flag_dist,
        "session_persist_fail_count": persist_fail_cnt,
        "memory_trim_events": trim_event_cnt,
    }


def latest_infra() -> dict:
    """取 infra.jsonl 最后一条巡检的磁盘水位"""
    recs = _read_jsonl(INFRA_PATH)
    if not recs:
        return {}
    return (recs[-1].get("disk") or {})


def judge_span_persist_rate() -> float:
    """评测域 span 落盘率（M5 数据源）；无 eval_traces 时返回 None（no_data）"""
    traces_dir = Path(__file__).resolve().parent / "results" / "eval_traces"
    if not traces_dir.exists():
        return None
    runs = list(traces_dir.glob("*.jsonl"))
    if not runs:
        return None
    # 简化判据：每个 run 文件是否含 eval_run span（收尾聚合已落盘）
    ok = 0
    for f in runs:
        try:
            if any('"span": "eval_run"' in ln or '"span":"eval_run"' in ln
                   for ln in f.read_text(encoding="utf-8").splitlines()):
                ok += 1
        except Exception:
            pass
    return round(ok / len(runs), 4)


# ---------- SLO 判定 ----------

_OPS = {
    ">=": lambda a, b: a >= b,
    "<=": lambda a, b: a <= b,
    ">": lambda a, b: a > b,
    "<": lambda a, b: a < b,
    "==": lambda a, b: abs(a - b) < 1e-9,
}


def resolve_metric(metric: str, agg: dict, infra: dict):
    """metric 名 → 实际值；无法计算返回 None（判为 no_data，不算违规）"""
    if metric in agg:
        return agg[metric]
    if metric == "disk_free_gb":
        return infra.get("C_free_gb")
    if metric == "judge_span_persist_rate":
        return judge_span_persist_rate()
    return None


def judge_slo(agg: dict, infra: dict) -> list:
    """逐条 SLO 判定 → [{layer,metric,op,value,actual,level,state}]"""
    try:
        cfg = json.loads(SLO_CONFIG.read_text(encoding="utf-8"))
    except Exception as e:
        return [{"error": f"slo_config 读取失败: {e}"}]
    out = []
    for s in cfg.get("slo", []):
        actual = resolve_metric(s["metric"], agg, infra)
        if actual is None:
            state = "no_data"
        else:
            op = _OPS.get(s["op"])
            passed = op(actual, s["value"]) if op else True
            state = "ok" if passed else s.get("level", "warning")
        out.append({**s, "actual": actual, "state": state})
    return out


def run_monitor(window: str, source: str) -> dict:
    recs = load_window(window, source)
    agg = aggregate(recs)
    infra = latest_infra()
    slo = judge_slo(agg, infra)
    criticals = [s for s in slo if s.get("state") == "critical"]
    warnings = [s for s in slo if s.get("state") == "warning"]
    return {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "window": window,
        "source": source,
        "aggregate": agg,
        "infra_latest": infra,
        "slo": slo,
        "critical_violations": criticals,
        "warning_violations": warnings,
        "has_critical": bool(criticals),
    }


def _print_summary(rep: dict) -> None:
    agg = rep["aggregate"]
    print("=" * 60)
    print(f"  运行监控报告  窗口={rep['window']}  source={rep['source']}")
    print("=" * 60)
    print(f"  请求量: {agg['request_count']}  状态分布: {agg['status_dist']}")
    print(f"  错误率: {agg['request_error_rate']}  降级率: {agg['degraded_rate']}  "
          f"中断率: {agg['interrupted_rate']}  LLM错误率: {agg['llm_error_rate']}")
    print(f"  TTFT  P50={agg['ttft_p50_ms']}ms  P95={agg['ttft_p95_ms']}ms")
    print(f"  耗时  P50={agg['duration_p50_ms']}ms  P95={agg['duration_p95_ms']}ms")
    print(f"  流式间隔中位数: {agg['stream_gap_median_ms']}ms  token累计: {agg['tokens_total']}")
    if agg.get("intent_dist"):
        print(f"  意图分布: {agg['intent_dist']}")
    print("-" * 60)
    print("  SLO 判定:")
    icon = {"ok": "[OK]  ", "warning": "[WARN]", "critical": "[CRIT]", "no_data": "[N/A] "}
    for s in rep["slo"]:
        if "error" in s:
            print(f"    ! {s['error']}")
            continue
        st = s["state"]
        actual = "N/A" if s["actual"] is None else s["actual"]
        print(f"    {icon.get(st, '[?]   ')} [{s['layer']}] {s['metric']} {s['op']} {s['value']}"
              f"  实际={actual}  ({st})")
    print("-" * 60)
    if rep["critical_violations"]:
        print(f"  [CRIT] 严重违规 {len(rep['critical_violations'])} 项: "
              f"{[s['metric'] for s in rep['critical_violations']]}")
    elif rep["warning_violations"]:
        print(f"  [WARN] 警告违规 {len(rep['warning_violations'])} 项: "
              f"{[s['metric'] for s in rep['warning_violations']]}")
    else:
        print("  [OK] 全部 SLO 达标（或 no_data）")
    print("=" * 60)


def main():
    ap = argparse.ArgumentParser(description="运行监控 + SLO 判定")
    ap.add_argument("--window", default="24h", choices=list(_WINDOWS.keys()))
    ap.add_argument("--source", default="production")
    ap.add_argument("--json", action="store_true", help="以 JSON 输出报告")
    args = ap.parse_args()

    rep = run_monitor(args.window, args.source)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = RESULTS_DIR / f"monitor_{time.strftime('%Y%m%d')}.json"
    try:
        out_path.write_text(json.dumps(rep, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as e:
        print(f"报告写入失败(降级): {e}")

    if args.json:
        print(json.dumps(rep, ensure_ascii=False))
    else:
        _print_summary(rep)
        print(f"报告已写入: {out_path}")
    sys.exit(1 if rep["has_critical"] else 0)


if __name__ == "__main__":
    main()
