# Temu 数字油画自动化系统 — 下一阶段 Codex Prompt

> 当前状态：STEP 1 与 Milestone 1 已完成。  
> 本阶段开发 **Milestone 1.5（成本/履约主数据）+ Milestone 2（商品主数据 + Listing Generator + Temu 批量上传 Excel）**。  
> 完成后停止，不提前实现 Temu API 自动提交。

## 一、当前业务事实

- Temu 市场：美国
- 商品：Paint by Numbers / 数字油画
- ERP：**方果 ERP**（已从店小秘切换）
- 供应商：领典，美国工厂
- 工厂基础报价已经导入 PostgreSQL
- 运费按尺寸和重量计算；V1 暂按平均 **4 USD/件**估算
- 线稿处理费：**每个新图案一次性收取，可重复使用，不按件重复收费**
- 工厂贴标服务：**免费，确认成本为 0**
- 已有工厂装盒打包标准、重量表、方果授权店铺下单流程、方果手工单流程和订单导入模板

## 二、开发边界

本阶段实现：

1. 成本与履约主数据基础
2. Design 主数据
3. Product / SKU 自动生成
4. 工厂报价自动匹配
5. 运费估算
6. Listing Generator
7. Temu 批量上传模板映射与 Excel 生成
8. Pre-flight Validation

本阶段不要实现：

- Temu Create Goods API 实际提交
- 核价 API
- ACCEPT / NEGOTIATE / REJECT
- AI 选品
- 竞品爬虫
- 方果自动下单
- 备货单自动化
- 标签 PDF 打印包
- 自动发货
- Finance Dashboard

---

# Milestone 1.5 — 成本与履约主数据

## 三、成本模型

必须区分：

### Design One-Time Cost

当前主要是：

```text
line_art_cost
```

线稿处理费属于 Design 级一次性成本。

建议 Design 支持：

```text
line_art_cost
line_art_cost_currency
line_art_cost_paid
line_art_cost_paid_at
line_art_reusable
```

禁止把线稿费永久加入每件 SKU 的 unit variable cost。

### Unit Variable Cost

当前：

```text
Unit Variable Cost
=
Factory Product Cost
+
Shipping Cost
```

贴标：

```text
label_service_cost = 0
label_service_cost_status = CONFIRMED
```

必须继续遵守：

```text
NULL != 0
```

---

## 四、Costing 模块

建立：

```text
modules/
└── costing/
    ├── schemas.py
    ├── factory_cost_resolver.py
    ├── shipping_cost_resolver.py
    ├── design_cost_service.py
    └── unit_cost_service.py
```

Costing 模块只负责计算成本。

不要在这里实现：

```text
ACCEPT
NEGOTIATE
REJECT
```

---

## 五、运费模型

实际运费未来按：

```text
尺寸 + 重量 + 包装方式
```

计算。

V1 使用：

```text
estimated_shipping_cost_usd = 4.00
shipping_cost_type = ESTIMATED_AVERAGE
```

该值必须来自配置或数据库，不允许硬编码。

设计上支持：

```text
ESTIMATED_AVERAGE
CALCULATED
ACTUAL
```

未来重量表和包装规则接入后切换到 `CALCULATED`。

---

## 六、汇率

工厂成本为 CNY，运费估算为 USD。

V1 不接实时汇率 API。

通过配置：

```text
USD_CNY_EXCHANGE_RATE
```

成本结果记录：

```text
exchange_rate
exchange_rate_source
exchange_rate_timestamp
```

V1：

```text
exchange_rate_source = MANUAL_CONFIG
```

所有金额继续使用 `Decimal`，禁止使用 float。

---

## 七、成本计算输出

示例：

```json
{
  "factory_cost_cny": "44.00",
  "shipping_cost_usd": "4.00",
  "exchange_rate": "...",
  "shipping_cost_cny": "...",
  "unit_variable_cost_cny": "...",
  "shipping_cost_type": "ESTIMATED_AVERAGE",
  "cost_completeness_status": "ESTIMATED"
}
```

---

## 八、包装与重量规则

工厂已提供：

```text
领典美区数字油画装盒打包标准说明9.10.docx
领典-美西数字油画工厂重量表 - 9.10.xls
```

本阶段允许建立：

```text
packaging_rules
product_weight_rules
```

包装规则至少支持：

```text
variant_type
colors_count_condition
width_cm
height_cm
box_length_cm
box_width_cm
box_height_cm
max_units_per_box
notes
source
```

重量规则至少支持：

```text
width_cm
height_cm
colors_count
variant_type
weight
weight_unit
source
```

如果旧 `.xls` 解析存在兼容问题，不允许猜数据。

允许先建立 Adapter、Parser、fixture 和待补数据状态。

不要因为物流精算未完成而阻塞 Milestone 2。

---

# Milestone 2 — 商品主数据 + Listing Generator

## 九、Design 主数据

每张图案必须有唯一：

```text
design_id
```

系统内部示例：

```text
DESIGN-CAT-000001
```

同时建立：

```text
factory_design_code
```

例如：

```text
CAT000001
```

两者必须分离。

原因：方果/工厂流程对文件命名有限制，工厂侧编码不应依赖内部含特殊字符的 Design ID。

---

## 十、工厂素材命名

实现命名与校验模块，但本阶段不上传方果。

例如：

```text
线稿：
CAT000001.jpg

说明书：
CAT000001@说明书.jpg
```

模块负责：

- 生成正确文件名
- 校验非法字符
- 保证线稿与说明书一一对应
- 保留 Design ID ↔ Factory Design Code 映射

---

## 十一、Product / SPU / SKU

一个 Design 对应一个 Product / SPU。

一个 Product 下可以有多个 SKU Variant。

建议 SKU：

```text
PBN-{factory_design_code}-{size}-{colors}-{frame}
```

例如：

```text
PBN-CAT000001-4050-24-U
```

含义：

```text
PBN = Paint by Numbers
4050 = 40x50
24 = 24 colors
U = UNFRAMED
F = FRAMED
```

编码规则必须：

- deterministic
- unique
- idempotent
- documented
- tested

---

## 十二、禁止生成工厂不存在的规格

SKU Generator 必须查询 Factory Quote Catalog。

只有存在有效报价的组合才能默认生成。

例如：

```text
24 colors
40x50
UNFRAMED
→ 有报价
→ ALLOW
```

如果：

```text
NO_QUOTE
```

则：

```text
DO NOT GENERATE
```

除非人工 override。

---

## 十三、SKU 成本匹配

流程：

```text
SKU
↓
colors_count + size + variant_type
↓
Factory Cost Resolver
↓
factory_costs
↓
Factory Product Cost
↓
Shipping Cost Resolver
↓
Estimated Shipping
↓
Unit Variable Cost
```

每个 SKU 必须能够追踪成本来源。

示例：

```json
{
  "factory_sku": "PBN-CAT000001-4050-24-U",
  "factory_cost": "44.00",
  "factory_cost_currency": "CNY",
  "factory_cost_source": "LINGDIAN / Sheet1 / row 10",
  "shipping_cost": "4.00",
  "shipping_currency": "USD",
  "shipping_cost_type": "ESTIMATED_AVERAGE"
}
```

---

## 十四、Listing Generator

建立：

```text
modules/
└── listing/
    ├── schemas.py
    ├── title_generator.py
    ├── attribute_mapper.py
    ├── sku_generator.py
    ├── image_mapper.py
    ├── listing_validator.py
    └── listing_service.py
```

V1 不需要复杂 AI。

优先：

```text
模板 + 结构化字段
```

确保生成结果稳定、可验证。

---

## 十五、Listing 输入

至少：

```text
Design ID
Factory Design Code
Title Base
Theme
Main Image
Additional Images
Available Variants
Product Type
Target Market
```

Target Market：

```text
US
```

---

## 十六、数字油画 Listing 属性

至少支持：

```text
尺寸
色数
是否带框
商品类型
主题
主图
附图
SKU
```

Temu 字段必须以真实 Temu 批量上传模板为准。

不要自行猜测 Temu 字段名或枚举值。

---

## 十七、尺码参数

数字油画不填写服装、鞋类等无关尺码字段。

优先使用真实类目模板要求的：

```text
长度
宽度
```

或：

```text
长
宽
高
```

不要同时重复填写两套尺寸属性，除非 Temu 模板明确要求。

---

## 十八、图片规则

每个 Design 至少必须有：

```text
main_image
```

缺主图：

```text
LISTING_INVALID
```

不得进入正式上传文件。

支持：

```text
additional_images
```

图片与 Design ID 必须稳定绑定，禁止仅通过文件显示名称模糊匹配。

---

## 十九、Listing Validation

进入正式导出前检查：

```text
Design ID exists
Factory Design Code exists
Main Image exists
At least one valid SKU
Every SKU has factory cost
Every SKU has shipping estimate
Every SKU has valid size
Every SKU has valid colors_count
Every SKU has frame status
No duplicate SKU
Required Temu fields complete
```

失败：

```text
INVALID
```

不进入正式上传 Excel。

---

## 二十、Pre-flight Validation

批量导出前生成报告，例如：

```text
Designs: 100
Products: 100
SKUs: 428

Valid Products: 96
Invalid Products: 4

Valid SKUs: 421
Invalid SKUs: 7

Missing Images: 2
Missing Factory Cost: 3
Invalid Attributes: 2
```

生成：

```text
listing_validation.xlsx
```

至少包含：

```text
summary
products
skus
issues
```

---

## 二十一、Temu 批量上传 Excel

本阶段最终核心输出：

```text
temu_batch_listing.xlsx
```

流程：

```text
真实 Temu 批量上传模板
+
Listing Data
↓
Template Mapper
↓
Excel Writer
↓
Validation
↓
temu_batch_listing.xlsx
```

必须在真实 Temu 模板基础上填值。

优先使用：

```text
openpyxl
```

尽量保留：

- 原模板格式
- Sheet
- 隐藏 Sheet
- 数据验证
- 公式
- 合并单元格
- 必填字段结构

不要使用 Pandas 粗暴重建整个 Workbook。

---

## 二十二、输出目录

推荐：

```text
outputs/
└── listings/
    └── {batch_id}/
        ├── temu_batch_listing.xlsx
        ├── listing_validation.xlsx
        ├── listing_manifest.json
        └── errors/
```

`listing_manifest.json` 至少记录：

```text
batch_id
design_count
product_count
sku_count
created_at
source_template
template_hash
```

---

## 二十三、Dry Run

实现：

```bash
python scripts/generate_temu_listing.py   --design-batch PATH   --template PATH   --dry-run
```

Dry-run：

- 不生成正式上传文件
- 输出商品数量
- 输出 SKU 数量
- 输出工厂成本匹配情况
- 输出运费估算情况
- 输出图片缺失
- 输出字段缺失
- 输出无报价规格
- 输出 Validation Report

确认后：

```bash
python scripts/generate_temu_listing.py   --design-batch PATH   --template PATH   --commit
```

---

## 二十四、本阶段禁止自动上架

即使发现 Temu Create Goods API 可用，本阶段也禁止提交真实商品。

允许：

```text
记录 API capability
设计 TemuListingAdapter interface
```

不允许：

```text
POST / Create Goods
真实上架
```

必须先证明：

```text
Design
→ Product
→ SKU
→ Factory Cost
→ Shipping Estimate
→ Listing
→ Temu Excel
```

全链路正确。

---

# 方果 ERP 边界

## 二十五、本阶段方果只做适配准备

当前 ERP：

```text
方果
```

已有：

```text
方果授权店铺下单流程.docx
方果手工单下单流程.docx
订单-导入模板.xlsx
```

本阶段不要实现自动推送订单到方果。

只允许：

1. 新增 `integrations/fangguo/`
2. 分析并记录订单导入模板字段
3. 定义未来 `FangguoOrderAdapter` interface
4. 保留 Design / Factory SKU / Factory Design Code 与方果商家编码的映射能力

下一阶段再实现：

```text
订单
→ 方果订单模板
→ 线稿 / 说明书
→ 三方面单
→ 工厂
```

---

# 二十六、测试要求

至少覆盖：

### Costing

- Factory cost 正确匹配
- NO_QUOTE 不生成成本
- $4 shipping estimate 正确读取配置
- 汇率使用 Decimal
- label cost = confirmed zero
- line art cost 不进入永久 per-unit cost

### Design

- Design ID 唯一
- Factory Design Code 唯一
- Factory Design Code 命名合法

### SKU

- 同输入生成相同 SKU
- 不重复
- NO_QUOTE 规格不生成
- framed / unframed 正确编码
- size 正确编码
- colors 正确编码

### Listing

- 缺图片失败
- 缺成本失败
- 无有效 SKU 失败
- duplicate SKU 失败
- 合法商品通过

### Excel

- 保留模板 Sheet
- 保留必要格式
- 正确写入字段
- 错误商品不进入正式文件
- workbook 可正常打开

---

# 二十七、验收场景

至少构造一个真实数字油画 Design：

```text
Design ID:
DESIGN-CAT-000001

Factory Design Code:
CAT000001
```

生成至少：

```text
PBN-CAT000001-3040-24-U
PBN-CAT000001-4050-24-U
```

其中：

```text
40x50 / 24 colors / UNFRAMED
```

必须能够匹配现有 Factory Quote Catalog：

```text
CNY 44.00
```

再加：

```text
Estimated Shipping = 4 USD
```

得到可追踪的 Estimated Unit Variable Cost。

然后成功进入 Listing 数据和测试用 Temu 批量上传 Excel。

---

# 二十八、完成后停止

完成 Milestone 1.5 和 Milestone 2 后停止。

不要进入：

```text
Temu API 自动上架
Pricing Engine
核价/议价
方果自动下单
备货单
标签 PDF
Finance Dashboard
```

完成后返回：

1. 新增 / 修改文件
2. 是否修改数据库 schema
3. 成本模型设计
4. 线稿一次性成本如何处理
5. 运费估算如何处理
6. 汇率如何处理
7. Design ID / Factory Design Code 规则
8. SKU 编码规则
9. 生成了多少测试 SKU
10. Factory Cost 匹配结果
11. Listing Validation 结果
12. Temu Excel 生成结果
13. Dry-run 示例
14. Commit 示例
15. 测试结果
16. 当前仍缺失的业务数据
17. 下一阶段建议

如果真实 Temu 批量上传模板尚未提供或字段不足：

不要猜字段。

先完成 Listing Domain Model 和 Template Adapter，并明确列出需要补充的真实模板/字段。

优先保证：

```text
正确
可追踪
幂等
可测试
可扩展
```

不要为了提前实现更多功能牺牲数据正确性。
