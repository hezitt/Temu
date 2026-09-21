# Temu 数字油画自动化系统

这是 Temu 美国跨境数字油画业务的数据库优先基础工程。当前已完成 **STEP 1、Milestone 1、Milestone 1.5**，并完成 **Milestone 2 的商品领域模型、预检报告和真实模板适配器**。工厂报价、包装规则和重量规则均可追溯写入 PostgreSQL；Listing 只从有效报价生成 SKU。数据库已经加入 Temu 自研应用与方果接口所需的店铺、授权连接、同步、事件、素材和发布任务基础表。

已接入真实 Temu 美国站半托管成人数字画套件模板。自研应用获批前，店小秘仍是唯一商品发布方，方果仍是唯一订单履约和发货回传方；自研商品应用验证通过后，商品写入责任将从店小秘切换到本系统。首个商品已通过店小秘人工提交、正在审核；店小秘页面显示的 SPU/SKC/SKU ID 已作为“待 Temu 卖家中心确认”的外部标识录入文件。尚未实现 Temu API 自动上架、定价/议价、方果自动下单、备货、标签 PDF 或 Finance Dashboard。

## 当前能力

- Python 3.12 + FastAPI 基础应用与无数据库依赖的 `/health` 探针
- PostgreSQL + SQLAlchemy 2 异步连接配置
- Alembic 版本化迁移，当前创建 30 张业务与支撑表
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
- `PBN-{factory_design_code}` 统一 SPU 货号与 `PBN-{factory_design_code}-{size}-{colors}-{U/F}` 确定性 SKU 编码
- Listing 依据尺寸、色数和框型自动解析工厂包装三边、重量、每箱上限及来源哈希
- Listing pre-flight 校验与 `summary/products/skus/issues` 四表报告
- 已审核真实 Temu 模板的 83 列映射和 `spu`/`sku` 分层行结构；dry-run 永不生成正式上传文件
- 同一 SPU 支持“型号（with frame/no frame）+ 尺码”两个 SKU 规格维度；SPU 层框架类型仍要求人工确认，系统不从其中一个 SKU 猜测
- 店小秘人工发布结果可按店铺同步至 `temu_listings`，分别保存店小秘 SPU、Temu SPU、SKC、SKU ID 和审核状态；默认 dry-run、重复执行幂等
- `stores` 和 `integration_connections` 分离店铺与外部授权；数据库只保存密钥引用、权限和到期时间，不保存明文 token
- 同步游标、运行记录、平台事件均具备幂等键、状态和失败信息，可安全重试
- Temu 素材上传与商品发布任务分别保存平台文件 ID、请求快照和执行结果
- 方果商家端只读客户端支持店铺、绑定工厂、订单 TID 分页和订单详情；没有暴露下单、取消或发货写方法
- 方果订单同步按美区半托管平台编号 `225` 拉取，并把消费者订单、明细、生产状态和运单安全落库
- 订单 SKU 同时使用系统货号和 Temu SKU ID 交叉匹配，冲突或无法匹配时进入人工复核
- 方果订单列表只支持支付时间筛选，系统保存支付时间水位并采用滚动回看窗口，避免把它误当成更新时间增量
- `/health/database` 独立检查 PostgreSQL 连接，避免把进程存活误当成数据库健康
- 美国 SDS 与欧盟 SDS 分开留档，且美国 SDS 不被误当作 ASTM D-4236 消费品标签证明
- Sorftime Temu 市场数据客户端支持 Base64+gzip 解码、响应缓存、额度账本和默认禁用真实请求

## 快速开始

要求：Python 3.12、PostgreSQL。也可以用 Docker Compose 启动本地 PostgreSQL。

```bash
cp .env.example .env
# 修改 .env 中的本地数据库密码，并同步修改 DATABASE_URL 中的密码。
make setup
docker compose up -d postgres
make upgrade
make run
```

访问 `http://127.0.0.1:8000/health` 检查应用进程，访问 `http://127.0.0.1:8000/health/database` 检查数据库连接。PostgreSQL 仅绑定 `127.0.0.1`，不会通过 Docker 端口暴露到局域网。

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

商品 intake 主数据同样先预检再提交。它会幂等写入 Design、Product、SKU，并为每个 SKU 绑定当前有效工厂报价：

```bash
python scripts/import_product_intake.py \
  --intake data/templates/first_product.intake.json \
  --supplier LINGDIAN \
  --dry-run
```

确认预检结果后改为 `--commit`，再运行店小秘外部 ID 同步。未配置人工汇率时会保留 4 USD 运费和工厂报价来源，但不会虚构完整人民币单件成本。

方果订单同步同样默认 dry-run。真实 Key 只写入本机 `.env` 的 `FANGGUO__API_KEY`，不要写入命令参数、日志或 Git：

```bash
python scripts/sync_fangguo_orders.py \
  --store-code US_MAIN \
  --dry-run
```

默认查询最近 180 分钟支付的 Temu 美区半托管订单，单页 100 条。预检确认后改为 `--commit`；重复窗口会幂等更新现有订单，不会重复创建订单和明细。

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

店小秘外部 ID 同步同样默认 dry-run。`--store-code` 应使用系统内稳定的店铺编码，而不是店铺展示名称：

```bash
python scripts/sync_dianxiaomi_listing.py \
  --intake data/templates/first_product.intake.json \
  --supplier LINGDIAN \
  --store-code US_MAIN \
  --dry-run
```

预览确认无误后改为 `--commit`。如需准确保留页面观察时间，可传入带时区的 `--observed-at`；未传时使用录入文件的修改时间。店小秘页面上的 SPU ID 不会自动冒充 Temu 卖家中心 SPU，只有录入文件的 `identifiers.temu_spu` 经确认后填写，系统才写入 `temu_spu`。

Sorftime Temu 市场数据调用默认只生成计划，不消耗额度：

```bash
.venv/bin/python -m scripts.sorftime_research \
  category-search --name "Adult Paint by Number Kits"
```

确认计划后，需要同时在未跟踪的 `.env` 中填写 `SORFTIME__ACCOUNT_SK`、把
`SORFTIME__LIVE_REQUESTS_ENABLED` 改为 `true`，并显式加入 `--execute` 才会真实请求：

```bash
.venv/bin/python -m scripts.sorftime_research --execute \
  category-search --name "Adult Paint by Number Kits"
```

已支持 `CategoryTree`、`CategorySearchFromName`、`CategoryRequest`、`ProductRequest`、
`ProductSearchFromName`、`ProductTrendRequest` 和 `ProductSearch`。解压后的响应与额度账本
保存在 `data/processed/sorftime/`，相同参数优先读取缓存，不重复消耗额度。
缓存默认有效24小时；刷新后仍保留按时间命名的原始快照，供后续趋势分析与审计。

Amazon 美国站使用同一 Sorftime 密钥和共享额度账本，但固定使用 `domain=1`。调用同样默认
只生成零成本计划；下面的命令预计消耗1次，但不会真实执行：

```bash
.venv/bin/python -m scripts.sorftime_amazon_research \
  category-search --name "paint by numbers for adults"
```

Amazon 适配器会动态计算组合历史类目、多 ASIN、长周期趋势和包含子体销量时的真实预计成本，
防止这些接口以固定成本显示而意外超额。

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
- `temu_listings`：店铺维度的店小秘 SPU、Temu SPU/SKC/SKU、Goods ID、平台审核状态与观察来源。
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

接口自动化基础表：

- `stores`：店铺、站点、跨境/本土类型与半托管模式。
- `integration_connections`：Temu、方果等授权连接；只保存 `credential_reference` 和 token 指纹。
- `integration_sync_cursors`：按连接和资源保存增量同步游标与水位时间。
- `integration_runs`：每次同步的方向、幂等键、计数、状态和错误。
- `platform_events`：Temu 回调事件收件箱，按外部事件 ID 去重。
- `platform_assets`：图片、SDS、说明书等文件的本地哈希和平台文件 ID。
- `listing_submissions`：商品创建、修改、状态同步和库存更新任务。

消费者订单读取表：

- `sales_orders`：按店铺和方果业务单号去重的消费者订单头，不保存收件地址。
- `sales_order_items`：订单明细、Temu SKU、系统货号及内部 SKU 匹配状态。
- `fulfillment_orders`：方果待整理、待推送、工厂待审、生产中和已打包状态。
- `sales_order_shipments`：订单明细中已出现的承运商和运单号。

完整关系图和主外键说明见 [数据库 ER 关系](docs/database-er.md)。

## 关键标识

- 所有表使用 UUID `id` 作为内部主键，避免业务编码变化破坏引用。
- `designs.design_code`：例如 `DESIGN-CAT-000001`，全局唯一。
- `skus.factory_sku`：内部统一 SKU 货号，在同一供应商内唯一；店小秘、方果均通过映射引用它。
- `temu_listings.dianxiaomi_spu_id`：店小秘界面生成的 SPU ID，不等同于已确认的 Temu SPU。
- `temu_listings.temu_spu`、`temu_skc_id`、`temu_sku_id`、`temu_goods_id`：均以 `store_code` 为作用域；未确认值允许为空。
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

真实 Temu 模板、字段映射、美国 SDS、包装说明和重量表已经接入。首个商品的工厂图案编码 `LD000001`、24 色和四个变体已经确认并人工提交审核。方果商家端只读客户端和订单落库流程已经完成模拟验证，仍需配置商家端 Key 后进行真实店铺的只读联调。系统侧仍缺少：本次实际选择的 SPU 框架类型属性；每个 SKU 的最终申报价格和库存快照；图案/图片商用权；当前颜料与美国 SDS 的书面对应；ASTM D-4236 毒理审核及最终包装标签证据；方果同码线稿与说明书文件；带时间戳的人工 USD/CNY 汇率；Temu 审核结果及卖家中心 ID 复核。后续自动生成商品时先运行 dry-run，预检无 ERROR 才允许 commit。方果真实订单联调、备货、正式标签、Pricing Engine 和 Temu API 仍属于后续里程碑。
