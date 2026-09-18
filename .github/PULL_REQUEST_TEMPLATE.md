<!-- 感谢贡献！请填写以下清单，帮助 reviewer 快速理解你的改动。 -->

## 改动类型 / Type
- [ ] 🐛 Bug 修复（关联 Issue：#____）
- [ ] ✨ 新特性（关联 Issue：#____）
- [ ] ♻️ 重构（不改变外部行为）
- [ ] 📝 文档 / 示例
- [ ] ⚙️ 工程配置（CI / 依赖 / 脚本）

## 变更说明 / Description
<!-- 一句话说清做了什么、为什么这么做。 -->

## 关联的主线 / Pillar
- [ ] Harness 内核　- [ ] 可观测　- [ ] 评测飞轮　- [ ] 业务服务　- [ ] 前端　- [ ] 其他

## 自检清单 / Checklist
- [ ] 本地 `pytest tests/unit -q` 全绿（Mock 模式，无需 API Key）
- [ ] 涉及评测逻辑的改动，已跑 `python tests/eval/run_eval_script.py` 且**未通过放宽期望值来"过门禁"**
- [ ] 新增/修改的公开行为已在 `CHANGELOG.md` 记录
- [ ] 未提交任何 PII、API Key、真实简历或 `data/` 运行时产物
- [ ] 新增示例（如有）可在 Mock 模式下直接运行
