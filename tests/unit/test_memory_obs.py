"""记忆观测单测：memory span/flag 抛出、短期压缩频繁、长期损坏容错、monitor 记忆聚合"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.memory.long_term import LongTermMemory
from app.memory.short_term import ShortTermMemory
from app.observability import memory_guard as mg
from app.observability.context import begin_context
from tests.eval import monitor


def test_trim_span_and_frequent_flag():
    """短期记忆：窗口裁剪产生 memory span，超阈值抛压缩频繁 flag"""
    ctx = begin_context(source="eval")
    stm = ShortTermMemory(max_messages=3, max_tokens=4000)
    for i in range(8):
        stm.add_message("user", f"消息{i}")
    trim_spans = [s for s in (ctx.get("spans") or [])
                  if s.get("span") == "memory" and s.get("op") == "trim"]
    assert trim_spans, "裁剪应产生 memory span"
    assert stm.trim_count >= mg.TRIM_FREQUENT_THRESHOLD
    assert "short_term_trim_frequent" in (ctx.get("memory_flags") or [])
    assert stm.health()["trim_count"] == stm.trim_count


def test_session_inject_flag():
    """中期记忆：有历史但注入 0 条 → context_not_injected flag"""
    ctx = begin_context(source="eval")
    mg.check_session_inject(history_count=4, injected=0)
    assert "context_not_injected" in (ctx.get("memory_flags") or [])
    mg.check_session_inject(history_count=4, injected=4)
    inject_spans = [s for s in ctx["spans"] if s.get("op") == "inject"]
    assert len(inject_spans) == 2
    assert "context_not_injected" in ctx["memory_flags"]  # 去重：只抛一次


def test_session_persist_failed_is_critical():
    """中期记忆：持久化失败抛 critical 级 flag"""
    ctx = begin_context(source="eval")
    mg.check_session_write(msg_count=4, error="disk full")
    assert "session_persist_failed" in (ctx.get("memory_flags") or [])
    assert mg.memory_status(ctx["memory_flags"]) == "critical"


def test_long_term_corrupt_load_degrades(tmp_path):
    """长期记忆：JSON 损坏不阻断初始化，降级默认值并抛 flag"""
    (tmp_path / "user_profile.json").write_text("{corrupt", encoding="utf-8")
    ctx = begin_context(source="eval")
    ltm = LongTermMemory(storage_path=str(tmp_path))
    assert ltm.user_profile.name == ""  # 降级为默认值
    assert "long_term_load_corrupt" in (ctx.get("memory_flags") or [])


def test_probe_long_term_storage(tmp_path):
    """长期记忆存储探针：损坏文件判 critical，空目录判 green"""
    (tmp_path / "user_profile.json").write_text("{bad", encoding="utf-8")
    bad = mg.probe_long_term_storage(tmp_path)
    assert bad["status"] == "critical" and bad["errors"]
    ok = mg.probe_long_term_storage(tmp_path / "sub")
    assert ok["status"] == "green" and not ok["errors"]


def test_monitor_aggregate_memory():
    """monitor 聚合：memory_flags/span/msg_persisted → 记忆指标"""
    recs = [
        {"status": "ok", "memory_flags": ["session_persist_failed"],
         "spans": [{"span": "memory", "op": "trim", "trimmed": 2}]},
        {"status": "ok", "memory_flags": ["short_term_trim_frequent"]},
        {"status": "ok", "msg_persisted": False},
        {"status": "ok"},
    ]
    agg = monitor.aggregate(recs)
    assert agg["memory_error_count"] == 1
    assert agg["memory_warn_count"] == 1
    assert agg["memory_error_rate"] == 0.25
    assert agg["session_persist_fail_count"] == 1
    assert agg["memory_trim_events"] == 1
    assert agg["memory_flag_dist"]["session_persist_failed"] == 1


def test_build_general_prompt_injects_history(monkeypatch):
    """中期记忆注入：general_chat prompt 含最近历史（接地摘要隔离 DB）"""
    from app.services.chat_engine import ChatEngineService
    monkeypatch.setattr(ChatEngineService, "_resume_summary", staticmethod(lambda: ""))
    eng = ChatEngineService.__new__(ChatEngineService)  # 跳过 __init__（不拉 DB/LLM）
    history = [
        {"role": "user", "content": "帮我评估这个岗位"},
        {"role": "assistant", "content": "评分结果78分"},
    ]
    prompt, injected = eng._build_general_prompt("刚才评分多少?", history)
    assert injected == 2
    assert "评分结果78分" in prompt
    assert prompt.endswith("用户: 刚才评分多少?")


def test_multi_turn_messages_persist_grow(tmp_path, monkeypatch):
    """中期记忆持久化回归：多轮对话 messages 逐轮增长落盘，且历史注入下轮 prompt。

    防回归：SQLAlchemy JSON 列原地 mutate + 同对象赋值不标 dirty，
    曾导致 commit 只写 updated_at、历史永远冻结在旧快照（多轮失忆）。
    """
    import asyncio

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    import app.services.chat_engine as ce
    from app.db.database import Base
    from app.db.models import ConversationRecord

    engine = create_engine(f"sqlite:///{tmp_path / 'mem.db'}")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    monkeypatch.setattr(ce, "SessionLocal", Session)
    monkeypatch.setattr(ce.ChatEngineService, "_resume_summary", staticmethod(lambda: ""))
    monkeypatch.setattr(ce, "_observe_reply", lambda *a, **k: None)  # 隔离质量抽样落盘

    prompts = []

    class FakeLLM:
        async def chat(self, messages):
            prompts.append(messages[-1]["content"])
            return "收到:" + messages[-1]["content"][:20]

        async def chat_stream_async(self, messages):
            prompts.append(messages[-1]["content"])
            yield "收到"

    eng = ce.ChatEngineService.__new__(ce.ChatEngineService)  # 跳过 __init__（不拉真 LLM）
    eng.llm_client = FakeLLM()

    resp1 = asyncio.run(eng.chat(None, "我叫小熊，做测试开发"))
    cid = resp1.conversation_id
    asyncio.run(eng.chat(cid, "我刚说我叫什么？"))

    async def _drain_stream():
        async for _evt in eng.stream_chat(cid, "再确认下我的职业"):
            pass

    asyncio.run(_drain_stream())  # 流式分支同覆盖（需消费完生成器才走到 commit）

    db = Session()
    try:
        conv = db.query(ConversationRecord).filter_by(id=cid).first()
        msgs = conv.messages or []
    finally:
        db.close()
    assert len(msgs) == 6, f"三轮对话应落盘 6 条消息(user3+assistant3)，实际 {len(msgs)}"
    assert "我叫小熊" in prompts[1], "第二轮 prompt 应注入第一轮历史"
    assert "我叫小熊" in prompts[2], "流式第三轮 prompt 应注入前两轮历史"


def test_session_anchors_long_range_recall(tmp_path, monkeypatch):
    """长程记忆锚点（H-002）：历史超 10 轮窗口时，首轮交换+关联岗位进 prompt 补回忆"""
    from datetime import datetime

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    import app.services.chat_engine as ce
    from app.db.database import Base
    from app.db.models import ConversationRecord, JobRecord

    engine = create_engine(f"sqlite:///{tmp_path / 'anchor.db'}")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    monkeypatch.setattr(ce, "SessionLocal", Session)
    monkeypatch.setattr(ce.ChatEngineService, "_resume_summary", staticmethod(lambda: ""))

    db = Session()
    job = JobRecord(title="杭州AI测试", company="某公司", location="杭州", data_json={})
    db.add(job)
    db.commit()
    db.refresh(job)
    msgs = []
    for i in range(6):  # 6 轮 = 12 条历史，超 10 条注入窗口
        msgs.append({"role": "user",
                     "content": "首轮问杭州AI测试岗位" if i == 0 else f"闲聊{i}"})
        msgs.append({"role": "assistant", "content": f"回复{i}"})
    conv = ConversationRecord(title="t", messages=msgs, context_job_id=job.id,
                              created_at=datetime.now(), updated_at=datetime.now())
    db.add(conv)
    db.commit()
    db.close()

    eng = ce.ChatEngineService.__new__(ce.ChatEngineService)
    db = Session()
    try:
        c = db.query(ConversationRecord).first()
        anchor_long = eng._session_anchors(c, 12)
        anchor_short = eng._session_anchors(c, 5)
    finally:
        db.close()
    assert "首轮问杭州AI测试岗位" in anchor_long, "超窗口应加首轮锚点"
    assert "杭州AI测试" in anchor_long and "某公司" in anchor_long, "应含关联岗位锚点"
    assert "首轮问杭州AI测试岗位" not in anchor_short, "窗口内不重复加首轮锚点"
    assert "杭州AI测试" in anchor_short, "岗位锚点始终在"

    prompt, injected = eng._build_general_prompt(
        "我第一轮问的岗位是什么?", msgs, anchor_text=anchor_long)
    assert injected == 10, "注入窗口上限 10 条"
    assert "首轮问杭州AI测试岗位" in prompt, "超窗口回忆靠锚点兜住"
    assert prompt.index("[会话锚点]") < prompt.index("user: 闲聊"), "锚点应在历史块之前"
