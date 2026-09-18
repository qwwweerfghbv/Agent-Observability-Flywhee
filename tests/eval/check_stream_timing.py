"""流式计时探针：验证 SSE delta 按 LLM 真实节奏到达（非整段突发）。

用法：python tests/eval/check_stream_timing.py [url]
默认 url: http://127.0.0.1:8000/api/chat/ai-stream（AI SDK 协议）
也兼容旧协议 /api/chat/stream（delta 字段）。

判定：相邻 delta 间隔中位数 >= 20ms → 真流式（打字机节奏）。
突发特征为间隔中位数 <= 5ms（帧积压后一次性喷完）；
总跨度仅作展示（短回复跨度天然小，不作硬门禁）。
背景：async 生成器内同步 for 迭代阻塞生成器曾导致事件循环阻塞、
SSE 帧积压后 4ms 内突发喷完，流式名存实亡（2026-09-10 修复）。
"""
import json
import sys
import time

import requests


def main():
    url = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000/api/chat/ai-stream"
    body = {"message": "从1数到20，每个数字一行", "conversation_id": None}
    timestamps = []
    t0 = time.time()
    with requests.post(url, json=body, stream=True, timeout=120) as resp:
        for line in resp.iter_lines():
            if not line:
                continue
            text = line.decode("utf-8")
            if not text.startswith("data: "):
                continue
            payload = text[6:]
            if payload == "[DONE]":
                break
            evt = json.loads(payload)
            if evt.get("type") == "text-delta" or evt.get("delta"):
                timestamps.append(time.time())

    if len(timestamps) < 2:
        print(f"FAIL: delta 数量不足 ({len(timestamps)})")
        sys.exit(1)

    gaps = [(timestamps[i + 1] - timestamps[i]) * 1000 for i in range(len(timestamps) - 1)]
    gaps_sorted = sorted(gaps)
    median = gaps_sorted[len(gaps_sorted) // 2]
    span = (timestamps[-1] - timestamps[0]) * 1000
    ttfb = (timestamps[0] - t0) * 1000
    print(f"delta数={len(timestamps)} TTFB={ttfb:.0f}ms 总跨度={span:.0f}ms 间隔中位数={median:.0f}ms")
    print("前15个间隔(ms):", [round(g) for g in gaps[:15]])
    if median >= 20:
        print("PASS: 真流式（打字机节奏）")
    else:
        print("FAIL: 疑似突发（流式退化）")
        sys.exit(1)


if __name__ == "__main__":
    main()
