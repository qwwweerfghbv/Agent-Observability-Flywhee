# 贡献指南 · Contributing

感谢你愿意让这个项目变得更好！无论是报 Bug、补文档、加示例，还是实现一个新特性，都非常欢迎。

## 一、快速上手开发环境

```bash
git clone https://github.com/qwwweerfghbv/Agent-Observability-Flywhee.git
cd Agent-Observability-Flywhee
python -m venv venv && source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                               # 默认 LLM_PROVIDER=mock，无需 API Key
```

**全程可在 Mock 模式下开发与验证**——不触网、不消耗任何 Token，保证贡献者零成本复现。

## 二、提交前自检

```bash
pytest tests/unit -q                        # 离线单测（Mock 模式）必须全绿
python examples/01_score_job_mock.py        # 示例即文档，保证可运行
python examples/02_observability_trace.py
python examples/03_hallucination_grounding.py
```

若改动涉及评测逻辑，请额外跑评测集：

```bash
python tests/eval/run_eval_script.py
```

> ⚠️ **评测门禁红线**：门禁变红时，正确做法是**修复产品代码**让质量真正达标，
> 而**不是**放宽评测用例的期望值（如扩大 score 区间、增加 recommendation 可选项）来「过门禁」。
> 「改题迁就实现」会让高风险场景失去区分力，是本项目明确禁止的反模式。

## 三、代码规范

- **模块解耦**：Agent 内核（`app/harness`）、模型适配（`app/llm`）、工具（`app/tools`）、记忆（`app/memory`）、可观测（`app/observability`）分层清晰，替换组件不应波及其他层。
- **类型注解**：新增/修改的公开函数请补 type hint。
- **配置外置**：任何密钥、端点走 `.env`，**严禁硬编码 API Key 或提交真实 PII**（真实简历、姓名、电话、邮箱）。
- **依赖锁版本**：新增依赖请在 `requirements.txt` 固定版本，避免 `latest` 导致他人拉下来跑不起来。
- **Lint**：CI 用 ruff 只拦截「真错误」（`E9,F63,F7,F82`：语法错误/未定义名等），不做风格挑刺。

## 四、提交与 PR 流程

1. 从 `main` 切出特性分支：`feat/xxx`、`fix/xxx`、`docs/xxx`。
2. 提交信息尽量遵循 [Conventional Commits](https://www.conventionalcommits.org/)：`feat:` / `fix:` / `docs:` / `refactor:` / `test:` / `chore:`。
3. 一个 PR 聚焦一件事，附上下述说明，并在 `CHANGELOG.md` 的 `Unreleased` 记一笔。
4. PR 描述请套用 `.github/PULL_REQUEST_TEMPLATE.md` 的清单。

## 五、目录约定

| 路径 | 用途 |
|------|------|
| `app/` | 生产源码 |
| `examples/` | 面向用户的可运行示例（Mock 模式，零 Key） |
| `tests/unit` `tests/integration` | 自动化测试（CI 执行） |
| `tests/eval/` | 评测飞轮：评测集、规则打分器、LLM Judge、Bad Case 回流 |
| `_dev/` | **开发期临时脚本/日志，已在 `.gitignore` 中，不入库** |
| `data/` | 运行时数据（DB、上传、可观测落盘），不入库 |

> 一次性调试脚本请放 `_dev/` 并以 `_` 前缀命名，**不要散落在仓库根目录**。

## 六、许可

提交即表示你同意你的贡献以 [MIT License](LICENSE) 发布。
