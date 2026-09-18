# -*- coding: utf-8 -*-
"""评测域 SpanRecorder（SDD §4.9 / §5.3，M5）

评测走**进程内直调**（eval_runner._execute_service 直接 new Service().parse()），
不经 ObservabilityMiddleware，故用**显式 SpanRecorder** 追加写
``tests/eval/results/eval_traces/{run_id}.jsonl``，不依赖 ContextVar 中间件。

四类 span：
  eval_run     run_cases 起止（start 带 total_cases；end 带 gate/tokens/hash）
  case         每条用例（module/status/duration_ms/service_ms/score_ms/weighted_score）
  service_call 被测服务进程内直调（service_name/in_process/duration_ms/degraded）
  judge_call   LLMJudgeScorer._call_judge（judge_type/prompt_hash/tokens/raw_reason/score/red_line）

设计要点：
  - emit 即追加写，报告中心可 tail 出 ``[done/total]`` live 进度（US-S7）
  - 静默降级：任何异常仅吞掉，绝不影响评测主链路
  - 活跃 recorder 用 ContextVar 保存，judge/service 调用点用 emit_span() 免传参
"""
import contextvars
import hashlib
import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.observability.writers import _append_jsonl

EVAL_TRACES_DIR = Path(__file__).resolve().parent / "results" / "eval_traces"

_active: contextvars.ContextVar[Optional["SpanRecorder"]] = contextvars.ContextVar(
    "eval_span_recorder", default=None
)


def compute_eval_set_hash(cases) -> str:
    """评测集内容 hash（US-S2）：用例集内容变更即变。

    写 ``eval_run`` span + 合入流水，用于"分数变化到底来自代码还是评测集"的归因。
    """
    try:
        items = []
        for c in cases:
            d = c.model_dump() if hasattr(c, "model_dump") else dict(c)
            items.append(json.dumps(d, ensure_ascii=False, sort_keys=True, default=str))
        return hashlib.sha256("\n".join(sorted(items)).encode("utf-8")).hexdigest()[:12]
    except Exception:
        return ""


class SpanRecorder:
    """评测链路 span 记录器：一个 run 一个 jsonl 文件，emit 即追加写。"""

    def __init__(self, run_id: str, base_dir: Optional[Path] = None):
        self.run_id = run_id
        self.base_dir = Path(base_dir) if base_dir else EVAL_TRACES_DIR
        self.path = self.base_dir / f"{run_id}.jsonl"

    def emit(self, span: str, span_id: str = None, parent: str = None, **attrs) -> None:
        rec = {
            "span": span,
            "run_id": self.run_id,
            "span_id": span_id,
            "parent": parent,
            "end_ts": round(time.time(), 3),
            "attrs": attrs,
        }
        _append_jsonl(self.path, rec)

    # 上下文管理器：进入即设为活跃 recorder，供 emit_span() 免传参使用
    def __enter__(self) -> "SpanRecorder":
        set_active_recorder(self)
        return self

    def __exit__(self, *exc) -> bool:
        set_active_recorder(None)
        return False


def set_active_recorder(rec: Optional[SpanRecorder]) -> None:
    try:
        _active.set(rec)
    except Exception:
        pass


def get_active_recorder() -> Optional[SpanRecorder]:
    try:
        return _active.get()
    except Exception:
        return None


def emit_span(span: str, span_id: str = None, parent: str = None, **attrs) -> None:
    """向当前活跃 recorder emit；无 recorder（如线上抽样评分）时 no-op。"""
    rec = get_active_recorder()
    if rec is not None:
        rec.emit(span, span_id=span_id, parent=parent, **attrs)


def read_eval_trace(run_id: str, tail: bool = False) -> Dict[str, Any]:
    """读评测链路 → span 树 + live 进度（API /eval-traces/{run_id}，US-S6/S7）。

    - progress.live：未落 ``eval_run(phase=end)`` 即视为仍在跑
    - total：优先取 eval_run span 的 total_cases，缺失时退化为已 emit 的 case 数
    """
    path = EVAL_TRACES_DIR / f"{run_id}.jsonl"
    spans: List[Dict] = []
    if path.exists():
        try:
            for line in path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    spans.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
        except Exception:
            pass

    eval_run_attrs: Dict[str, Any] = {}
    finished = False
    for s in spans:
        if s.get("span") == "eval_run":
            a = s.get("attrs", {}) or {}
            eval_run_attrs.update(a)
            if a.get("phase") == "end":
                finished = True
    cases = [s for s in spans if s.get("span") == "case"]
    done = len(cases)
    total = eval_run_attrs.get("total_cases") or done
    current = cases[-1].get("span_id") if cases else None
    return {
        "run_id": run_id,
        "source": "eval",
        "progress": {"done": done, "total": total, "current": current,
                     "live": bool(spans) and not finished},
        "eval_run": eval_run_attrs,
        "spans": spans[-200:] if tail else spans,
    }
