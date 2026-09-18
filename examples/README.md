# 示例 · Examples

**全部示例默认运行在 Mock 模式，无需任何 API Key、不消耗任何 Token**，复制即可跑通。

## 运行前提

```bash
cd job-agent
pip install -r requirements.txt
```

> 示例内部通过 `set_llm_client(MockClient())` 显式注入 Mock 客户端，因此**无需**先创建 `.env` 也能直接运行。

## 示例清单

| 示例 | 演示内容 | 运行 |
|------|----------|------|
| [01_score_job_mock.py](01_score_job_mock.py) | 业务链路最小闭环：简历 + 岗位 → 5 维加权评分与建议 | `python examples/01_score_job_mock.py` |
| [02_observability_trace.py](02_observability_trace.py) | **核心差异化**：一次请求如何被采集为结构化 Trace（trace_id / spans / 版本快照 / 延迟 / token） | `python examples/02_observability_trace.py` |
| [03_hallucination_grounding.py](03_hallucination_grounding.py) | 幻觉防线：系统提示如何注入「当前日期 + 唯一事实依据 + 不得编造」 | `python examples/03_hallucination_grounding.py` |

## 想跑完整应用？

示例只演示内核能力。要体验带 React 大盘的完整应用（对话 / 简历 / 岗位 / 投递 / 可观测），请看仓库根 [README 的「快速开始」](../README.md#快速开始)：

```bash
cp .env.example .env          # 保持 LLM_PROVIDER=mock
uvicorn app.main:app --port 8000
# 打开 http://127.0.0.1:8000
```

## 接入真实大模型

把 `.env` 里的 `LLM_PROVIDER` 改为 `qwen` 或 `openai` 并填入 Key 即可；示例中的 `set_llm_client(MockClient())` 换成 `LLMClientFactory.create()` 就会走真实模型。凡兼容 OpenAI 协议的服务，配置 `OPENAI_BASE_URL` 即可接入。
