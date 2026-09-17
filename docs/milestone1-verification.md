# Milestone 1 验证记录

验证日期：2026-09-15（Asia/Shanghai）。

## 真实 PostgreSQL

- 本机没有 Docker，因此从 PostgreSQL 官方发布源构建临时 PostgreSQL 16.15，仅安装到 `/tmp`。
- Alembic 实际执行并通过：`0001 → 0002 → 0001 → 0002`，最终版本为 `20260915_0002 (head)`。
- 首次迁移验证发现枚举检查约束被重复创建；修复后完整升级和降级链通过。
- 使用真实源文件提交后，`factory_costs` 有 73 条当前成本记录；再次普通提交被文件 SHA-256 去重拒绝；`--force` 复跑新增 0、更新 0、未变化 73，当前业务键重复数为 0。

## 源文件结果

- SHA-256：`71cacd77bd248d924e6286810a40750deabc2d9dcf6c7d38a3d01c46a391e64b`
- 解析候选：92
- 有效报价：73
- WARNING：0
- ERROR：0
- SKIPPED：19（13 个 `NO_QUOTE`，6 个 `SEPARATOR_ROW`）
- 正式成本中 0 元记录：0
- 73 条记录的物流、包装、标签和总变动成本都为 `NULL`，完整性均为 `INCOMPLETE`。

验收样例：`LINGDIAN / 24色 / 40x50 / UNFRAMED = CNY 44.00`，来源为 `Sheet1` 第 10 行，`shipping_included=false`。

## 测试

- Pytest：38 项通过，其中包含真实 PostgreSQL 集成测试。
- Ruff：通过。
- Mypy：通过。
- 两份最终 Excel 报告均以 Artifact Tool 复核 3 个工作表，并完成公式错误扫描和逐表渲染检查。
