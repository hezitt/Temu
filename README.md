# Temu 数字油画自动化系统

这是 Temu 美国跨境数字油画业务的数据库优先基础工程。当前已完成 **STEP 1、Milestone 1、Milestone 1.5**，并完成 **Milestone 2 的商品领域模型、预检报告和真实模板适配器**。工厂报价、包装规则和重量规则均可追溯写入 PostgreSQL；Listing 只从有效报价生成 SKU。

由于尚未提供真实 Temu 商品批量上传模板，本轮不会猜 Temu 字段，也不会生成伪造的正式上传文件。没有实现 Temu API 自动上架、定价/议价、方果自动下单、备货、标签 PDF 或 Finance Dashboard。

## 当前能力

- Python 3.12 + FastAPI 基础应用与无数据库依赖的 `/health` 探针
- PostgreSQL + SQLAlchemy 2 异步连接配置
- Alembic 首次迁移，创建 16 张业务与支撑表
- `.env` 覆盖 `settings.yaml` 的分层配置
- 毛利阈值作为配置和可版本化数据库规则保存，不写死在业务逻辑中
- UUID 内部主键、稳定业务编码、外键、唯一约束与关键数值约束
- 导入批次和审计日志，为 Excel/API/人工/浏览器来源保留追踪链
- 工厂报价表解析、规范化、独立异常检测、Excel 校验报告与可追溯入库
- 文件 SHA-256 去重、`--force` 安全复跑、成本版本化和前后值审计
- Design ID 与 Factory Design Code 分离；方果线稿/说明书命名成对校验
- 线稿费作为 Design 一次性成本，不进入 SKU 永久单件变动成本
- 从配置读取 4 USD 平均运费；人工汇率与时间戳缺失时阻止完整成本提交
- 解析工厂 DOCX/XLS：36 条包装规则、82 条重量规则，来源哈希可追踪
- `PBN-{factory_design_code}-{size}-{colors}-{U/F}` 确定性 SKU 编码
- Listing pre-flight 校验与 `summary/products/skus/issues` 四表报告
- 真实 Temu 模板 + 审核后的字段映射才能生成正式工作簿；dry-run 永不生成正式上传文件

## 快速开始

要求：Python 3.12、PostgreSQL。也可以用 Docker Compose 启动本地 PostgreSQL。

```bash
cp .env.example .env
make setup
docker compose up -d postgres
make upgrade
make run
```

访问 `http://127.0.0.1:8000/health` 检查应用进程。`/health` 不代表数据库已经连通；数据库迁移成功才表示数据库配置可用。

常用命令：

```bash
make test
make lint
make migration m="describe change"
make upgrade
make downgrade
```

工厂报价默认 dry-run：

```bash
python scripts/import_factory_quote.py \
  --file "data/raw/领典数字油画最新报价.xlsx" \
  --supplier LINGDIAN \
  --dry-run
```

确认报告后再提交：

```bash
python scripts/import_factory_quote.py \
  --file "data/raw/领典数字油画最新报价.xlsx" \
  --supplier LINGDIAN \
  --commit
```

可选参数为 `--sheet`、`--force`、`--output-dir` 和 `--effective-date`。每次运行都会在 `outputs/imports/{batch_id}/factory_quote_validation.xlsx` 生成包含 `summary`、`normalized`、`issues` 的校验工作簿。完全相同且已成功提交的文件默认拒绝再次导入；只有显式指定 `--force` 才会重处理，成本业务键仍保持幂等。

工厂履约规则默认 dry-run；确认后把 `--dry-run` 改为 `--commit`：

```bash
python scripts/import_fulfillment_rules.py \
  --packaging-docx "/path/to/领典美区数字油画装盒打包标准说明9.10.docx" \
  --weight-xls "/path/to/领典-美西数字油画工厂重量表 - 9.10.xls" \
  --dry-run
```

Listing dry-run：

```bash
python scripts/generate_temu_listing.py \
  --design-batch data/templates/design_batch.example.json \
  --template "/path/to/real-temu-template.xlsx" \
  --mapping "/path/to/reviewed-temu-mapping.json" \
  --supplier LINGDIAN \
  --dry-run
```

正式生成前必须配置人工汇率及时间戳，并把 `--dry-run` 改为 `--commit`。Commit 只生成本地 Excel，不调用 Temu API。

## 配置

- `settings.yaml`：非敏感默认值，包括毛利阈值、币种、导入缺失标记和目录。
- `.env`：本机数据库凭据和环境覆盖，不提交到版本库。
- `.env.example`：可复制的环境变量模板。
- 嵌套环境变量使用双下划线，例如 `PRICING__TARGET_MARGIN=0.35`。
- 完整成本要求同时设置 `COSTING__USD_CNY_EXCHANGE_RATE` 和 `COSTING__EXCHANGE_RATE_TIMESTAMP`；V1 来源固定为 `MANUAL_CONFIG`。

默认规则为：目标毛利率 35%，最低毛利率 30%，高影响动作要求先 dry-run。后续定价实现应读取 `pricing_rule_sets` 中的生效版本，并把本次使用的阈值快照写入 `pricing_decisions`。

## 数据库表

需求指定的 12 张核心表全部存在：

- `designs`：图案主数据，`design_code` 是外部稳定 Design ID。
- `products`：SPU 级内部商品，与一个图案关联。
- `skus`：尺寸、色数、带框状态组成的可生产变体；保存 Factory SKU 和 Temu SKU。
- `factory_costs`：按供应商、规格、带框状态和生效日版本化的成本记录。
- `temu_listings`：店铺维度的 Temu SPU、Goods ID 与上架状态。
- `pricing_quotes`：Temu 原始核价记录。
- `pricing_decisions`：成本、毛利、规则、决定、dry-run 和执行结果的不可丢失快照。
- `stock_orders`：Temu 备货单头、状态和最终供应商文件路径。
- `stock_order_items`：原始 Temu SKU、匹配结果、数量和生产快照。
- `labels`：标签类型、版本、原文件、打印数量与状态。
- `shipments`：人工录入的承运商、追踪号、发货时间和箱数。
- `financial_transactions`：收入、结算、采购、定制、包装、物流、标签、退款等明细流水。

另有 4 张支撑表：

- `suppliers`：供应商主数据，避免把工厂信息散落在 SKU 和订单中。
- `import_batches`：来源文件哈希、批次状态、成功/失败行数和错误报告。
- `pricing_rule_sets`：可版本化的毛利阈值与独立议价策略配置。
- `audit_logs`：所有自动动作、dry-run、前后数据、结果和关联 ID。

完整关系图和主外键说明见 [数据库 ER 关系](docs/database-er.md)。

## 关键标识

- 所有表使用 UUID `id` 作为内部主键，避免业务编码变化破坏引用。
- `designs.design_code`：例如 `DESIGN-CAT-000001`，全局唯一。
- `skus.factory_sku`：在同一供应商内唯一。
- `skus.temu_sku`：V1 单店范围内唯一，可为空直到 Temu 分配。
- `temu_listings.temu_goods_id`、`temu_spu`：以 `store_code` 为作用域。
- `stock_orders.stock_order_code`、`shipments.shipment_code`：外部业务单号，唯一。
- 导入行绝不通过商品名称匹配。商品链路使用 Design ID、Factory SKU、Temu SKU 和数据库外键。

## 工厂报价导入规则

详细的来源核对见 [工厂报价表检查](docs/factory-quote-findings.md)。关键处理原则：

- 表内有 43 个色数/尺寸行，画芯与框画分列；拆分后解析 92 个候选，其中 73 个有有效报价。
- `/`、空白、`NULL`、`N/A`、`-` 都是 `NO_QUOTE`，只保留原始导入行，不创建 `factory_costs`。
- 分隔行中的 0 不是有效价格，会标记为 `SEPARATOR_ROW`；普通规格的 0 则是阻止入库的 `ZERO_COST` ERROR。
- 表头没有明确币种。根据业务文档暂按 CNY 配置，但正式导入前应确认。
- 价格明确为“未包邮价”，物流、包装、标签等成本缺失时均保存为 `NULL`，`total_variable_cost` 为 `NULL`，`cost_completeness_status=INCOMPLETE`。
- 里程碑说明称 `16色 / 20×20cm / 框画` 为 9，但当前源文件 `Sheet1!E4` 实际是空共享字符串。因此本次将它按 `NO_QUOTE` 保存，未虚构价格；异常检测器的独立测试证明如果源值确为 9，会保留 9 并标记 `SUSPICIOUSLY_LOW_COST` WARNING。
- 线稿处理费描述为按图收取且可复用。后续需要明确它是一次性设计费还是应按销量分摊，当前不直接计入单件变动成本。

## 数据建模原则

- PostgreSQL 是 Single Source of Truth；Excel/CSV 只是可追溯的输入输出渠道。
- 原始输入通过 `import_batches` 和各表的 `raw_payload`/来源字段保留证据。
- 外部系统回传必须提供 `idempotency_key` 或外部唯一键，避免重复入账或重复执行。
- 成本、核价、决定都按时间和版本保存快照，不覆盖历史。
- 未匹配的备货/财务行可以先保存原始外部 SKU，并以 `match_status` 进入人工复核；只有匹配成功后才允许进入 READY 流程。
- 标签保留原文件与处理后文件路径、SHA-256、版本和数量；生成打印包不能删除原文件。
- 发货仅支持人工记录，当前没有自动发货逻辑。

## 项目结构

```text
app/                 FastAPI 入口
core/                配置、数据库、日志
models/              SQLAlchemy 2 数据模型
alembic/              数据库迁移
modules/factory_quotes/  报价解析、规范化、校验、异常检测和幂等写入
integrations/excel/      Excel 读取与校验报告 Adapter
services/                报价导入应用服务
scripts/                 工厂报价导入 CLI 与报告渲染器
repositories/         数据访问层
schemas/              Pydantic DTO
jobs/                 调度任务
dashboard/            Dashboard 边界（当前仅占位）
data/                 原始、清洗和模板数据目录
outputs/              生成文件目录
docs/                 ER 与来源分析
tests/                   单元测试与可选 PostgreSQL 集成测试
```

## 当前阻塞与下一步

正式 `temu_batch_listing.xlsx` 仍需：真实 Temu 美国站目标类目的批量上传模板、审核后的字段/枚举映射、真实主图，以及带时间戳的人工 USD/CNY 汇率。补齐后先运行 dry-run，预检无 ERROR 才允许 commit。下一阶段仍需单独确认后才能进入方果订单、备货、标签、Pricing Engine 或 Temu API。
