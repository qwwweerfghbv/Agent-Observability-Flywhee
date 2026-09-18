# 更新日志 · Changelog

本项目的所有重要变更都会记录在此文件。

格式遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，
版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

## [Unreleased]

### Added
- 工程化配套：GitHub Actions CI（Mock 模式离线单测 + 示例冒烟 + ruff 关键规则 lint）。
- Issue 模板（Bug / Feature）与 Pull Request 模板。
- `CONTRIBUTING.md` 贡献指南（含评测门禁红线说明）。
- `examples/`：3 个零 API Key 可运行示例（岗位评分 / 可观测 Trace / 幻觉接地防线）。

### Changed
- 根目录一次性开发脚本统一归档至 `_dev/`（不入库），保持仓库根目录整洁。

## [0.3.0]

### Added
- **Harness 工程内核**：模型与执行分离、工具调用前权限/沙箱拦截、完整轨迹可审计回放、会话状态可恢复、轮次上限/超时/终止策略等循环保护。
- **求职业务全链路**：简历解析、岗位评分（5 维加权）、简历优化（真实性约束）、面试模拟（技术/行为/HR）、投递追踪。
- **React 前端**：由 Streamlit 迁移至 React 18 + Vite + Vercel AI SDK，后端单端口托管构建产物。
- **七层可观测平台**：Trace 链路追踪、请求级埋点、在线质量哨兵、安全扫描（注入/敏感信息）、记忆健康监测、SLO 告警、0-100 健康分，配可视化大盘。
- **评估驱动飞轮**：多层评测集 + 规则打分器 + LLM Judge + 线上 Bad Case 自动回流 + 人工评审合入 + 版本回归对比。
- **幻觉与长程记忆治理**：会话结构化锚点注入、以库内简历为「地面真相」的在线幻觉检测、长期记忆存储探针。
- **零门槛体验**：内置 `MockClient`，`LLM_PROVIDER=mock` 即可无需任何 API Key 跑通全链路。

[Unreleased]: https://github.com/qwwweerfghbv/Agent-Observability-Flywhee/compare/v0.3.0...HEAD
[0.3.0]: https://github.com/qwwweerfghbv/Agent-Observability-Flywhee/releases/tag/v0.3.0
