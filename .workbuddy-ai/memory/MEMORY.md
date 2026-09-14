# 仓储管理 ERP —— 项目长期记忆

> 跨会话有效的项目决策与约定。每日进展见同目录 `YYYY-MM-DD.md`。
> **唯一权威设计文档：`代发仓ERP_正式设计文档_v1.2.md`（工作区根目录）**。后续所有变更直接改它并记在「变更记录」。
> 原 `代发仓ERP_方案确认纪要_2026-09-14.md` **已被用户删除**，其结论已全部并入设计文档。

## 项目定位

跨境**代发仓 / 一件代发**（3PL 履约）。不是通用电商 ERP，**不接任何平台订单 API**。核心链路：运营粘贴订单号 → 关联产品货号 → 仓库执行 → 结果回传运营。

## 已确认的技术决定（全部拍板，勿再问）

| 项 | 决定 |
|---|---|
| 数据库 | **PostgreSQL**（2026-09-14 由 MySQL 改，用户主动放开原「硬约束」） |
| 后端语言 | **Python**（用户拍板：「就 py 吧，省的大改了」） |
| 前端 | **React**，两套独立前端（运营端 + 仓库端） |
| 仓库端底座 | **sentry-wms**（hightower-systems/sentry-wms，Apache-2.0） |
| 商品主数据 | 表结构抄 ModernWMS（category 树 + spu + sku），实现自研 |
| 部署 | 本地小服务器，统一部署 |
| 仓库硬件 | PC 后台 + PDA/扫码枪，**本质是两套界面** |
| 中枢框架 | **FastAPI**（独立进程，不塞进 sentry-wms 的 Flask） |
| 登录体系 | 运营端与仓库端**各自独立**（两套账号、两套会话，互不打通） |
| 仓库侧角色 | 只用 sentry-wms 的 `ADMIN`，**不需要**非管理员的仓库账号 |

**PG 路线的连锁影响**：sentry-wms 由「需 PG→MySQL 移植（估 2–4 周）」变为**可直接复用**；其 65 张表 / 74 个迁移 / 15 种版本化事件全部原生可用。唯一新增成本是 PG 运维熟悉度。

## 架构：两端 + 一个中枢（不可省）

运营端 ~20%（提交/查状态/二次确认）｜中枢 ~30%（提交单、订单号↔货号关联、状态机、库存流水、派发回传）｜仓库端 ~50%（主战场）。

**中枢层必需**：开源 WMS 的订单模型要求「建单时货号 + 数量齐全」，本项目是「先建单 → 后定货号 → 最后定数量」三步凑齐 → 不兼容，必须加「提交单」承接。

## 状态机（6 主状态 + 1 驳回回路）

`1 待仓库处理 → 2 待一次确认·货号 → 3 待二次确认·数量 → 4 待作业 → 5 作业中 → 6 已发货·完成`（状态 2 可驳回回到 1）

## 已确认的业务规则

**提交单 = 批次**（2026-09-14 确认）：默认含 **1 个订单号**，**可新增多个订单号**。三层结构：
`submission`（批次）→ `submission_order`（订单号，1..N）→ `submission_line`（明细行）。

**提交单行结构**（每行两个输入框，另加新品分支）：
- **货号**：老品填货号，走运营端「货号检索」（搜商品名 → 弹货号 → 填入）
- **商品名称/描述**：自由文本，**可留空**（知道货号就只填货号即可）
- **新品**：勾「新品申请货号」+ 选**二级类目**；系统生成「待审核货号」→ 仓库填**商品名**并确认非重复品 → 转正式号
- **数量字段在提交页不渲染**（二次确认时运营仍要填，提交后锁定，双确认流程不变）

**类目结构**：**固定两层**（一级 `家居用品` → 二级 `杯具`）。**`code_prefix` 只挂二级类目**。
第三层「玻璃杯 / 马克杯」是**商品名**，不是类目，**由仓库填写**，落在 `sku.item_name`。
取号例：`家居用品-杯具` = `A001` → 玻璃杯 `A001-1`，马克杯 `A001-2`。

**发货判定**：以**「单个订单」**为最小发货单位 —— **全有才发，缺一不发**。缺货订单标 `shortage` 等补货，**其他订单照常发**。不做部分发货。

**运营的操作边界**：运营提交数量（状态 ③→④）之后，**对该批次不能再做任何操作**（不能改数量、不能改货号、不能取消）。取消仅限状态 ①–③。

**驳回**：触发点是 ②→①。**粒度 = 按订单**（哪个订单货号有问题就驳哪个，其他订单不受影响）；**确认仍是整批**（一次确认所有待确认订单）。必须填原因，**订单级最多 3 次**（`reject_count`）。驳回后批次回到 ①，但其他已确认订单保持确认态；仓库改完号 → 该订单回到待确认。

**订单级两个状态字段**（`submission_order`）：
- `confirm_status`：`pending` / `confirmed` / `rejected` —— 管确认阶段（批次 ①–②）
- `status`：`pending` / `ordered` / `shortage` / `shipped` / `cancelled` —— 管作业阶段（批次 ④ 之后）

**商品主数据只有两张表**（**已砍掉 `spu`**）：`category`（两层）+ `sku`（`sku_code` 货号 / `item_name` 商品名 / `category_id` 二级类目 / `code_status`）。`inventory_ledger` **确认保留**，数据来源 = 订阅 `inventoryadjusted.completed` 事件写入。

**其他**：
- 类目表**由仓库手工建**；初始表已给占位（见设计文档 §2.2.1）
- 物流单号**不接 API，仓库手动录入**
- **采购单不纳入本期**（补货走「收货」，不进采购单流程）
- **退货流程本期就做**
- 仓库**可以修改**运营填的货号
- 超时：**1h 提醒当前该动的责任方；2h 两侧同时提醒并标红**；按状态分环节独立计时，状态推进/驳回/仓库处理完都重置

## ⚠️ 用户明确否定过的设计（不要重犯）

| 原设计 | 修正 |
|---|---|
| 用**商品名**匹配货号 | ❌ 匹配动作在**运营侧**（运营自己检索填号），仓库不猜货号 |
| 仓库录入发货数量 | ❌ 数量由**运营在二次确认时**填写 |
| 单一「二次确认」 | ❌ 拆成**第一次确认（货号）+ 第二次确认（数量）** |
| 提交单一对一（一单一商品） | ❌ 支持**多 SKU 行**，每行独立选货号或勾新品申请 |
| 新品建号直接生效 | ❌ 先落「**待审核货号**」，仓库确认非重复品才转正 |
| 待审核号保留/标记废弃 | ❌ 判重时**直接删掉**，该行改用已有货号 |
| 「关联后不可改」= 全锁死 | ❌ 锁定的是**货号关联**，可改的是**发货数量** |
| 数据库必须 MySQL | ❌ 2026-09-14 改为 PostgreSQL |

## 货号编码规则

类目树（自引用 `parent_id`）+ 每类目挂编码前缀 → 货号 = `前缀-序号`（如 `A001-1`）。`code_status` 区分 `draft`（待审核）/ `active`（正式），转正 = 改状态位，不另开表。判重时**删掉待审核号**。

## 底座选型结论：sentry-wms

对比 GreaterWMS 后选定。**决定性理由不是功能数量，是三点**：
1. **有对外连接层** —— `external_id`(UUID) 双向映射 + 15 种版本化事件 + Webhook + `idempotency_key` 幂等键。这正好是「中枢 ↔ 仓库端」要用的东西；GreaterWMS 完全没有，全要自研。
2. **前端是 React**，与项目已定的两套 React 同栈；GreaterWMS 是 Quasar(Vue)，等于多养一套前端技术栈。
3. **权限是真实实现的**（ADMIN/USER + `user_page_permissions` 页面级授权）；GreaterWMS 的 `utils/permission.py` **全部注释掉、`return True`**，是空壳。

**已知风险**：★22、2026-04 建仓，上游可能烂尾。缓解：Apache-2.0 可 fork 冻结；代码完成度高（65 表 / 74 迁移 / 15 事件），真风险是「上游不更新」而非「代码不能用」。

## 退货（RMA）设计 —— 本期要做

sentry-wms 的做法，本项目照抄精简：
- **退货不是新单据，是「订单的一种类型」**：`order_type='return'`，`so_number = <原单号>-RMA`，`parent_so_id` 指回原单。**不建独立 rma 表**，复用订单表 + 明细表。
- **建单不动物流、不动钱**：只插单头 + 明细行，状态 `OPEN`，行上记 `quantity_ordered`（预计退量）+ `original_so_line_id`。
- **收货复用入库流程**：`item_receipts` 加 `so_id`/`so_line_id` 两列；PO 收货填 `po_id`，退货收货填 `so_id`，同表同流程。
- **处置用「入哪个库位」表达**：入可售位 → 回库存；入不良品/开箱位 → 隔离。不另设「处置方式」字段。
- **状态**：`OPEN → PARTIALLY_RECEIVED → RECEIVED`。超收直接报错（`remaining = ordered - received`）。
- **幂等**：`idempotency_key` 直接当 `item_receipts.external_id`（UNIQUE），重复提交返回上次结果，不重复加库存。
- **收货记录 append-only，无作废路径**：收错 → 建**冲正 RMA**，绝不 void。
- **整单作废**：`voided_at`/`voided_by` 软删除，门槛是「仅 OPEN、未收货、无关联退款」，保证不会让已入库的货凭空消失。

## 实施进展（2026-09-14 更新）

14 条未决事项**已全部裁决**（裁决表见设计文档 §7.3），且设计已落地为代码：**P0–P2 完成，P3 部分完成**，**两端 UI 均已齐备**。权威进度见设计文档 **§5.4.1**。

| 阶段 | 状态 | 关键产物 |
|---|---|---|
| P0 地基 | ✅ | `db/migrations/001_hub_schema.sql`（`hub` schema 11 表，含类目/取号/删号约束与触发器）、`db/seeds/001_placeholder_categories.sql`、`db/checks/self_check.sql`、原子取号 |
| P1 中枢主干 | ✅ | 提交单三表 + 状态机 ①–③ 接口、`frontend-ops` 3 屏（运营端） |
| P2 仓库接入 | ✅ | 仓库端接口 + **仓库端 3 屏**（`wms/admin` 里的提交单核验/新品审核/类目管理）、下单适配器、webhook 消费端（验签+去重+状态映射）、超时后台扫描 |
| P3 退货与收尾 | ⚠️ 部分 | **中枢侧无退货接口** —— 退货完全由 sentry-wms 原生承载，中枢只订阅 `return.received` 写流水 |

**仍未做**：真实环境联调。本机无 Docker，跨系统「推」（下单）与「拉」（webhook）**从未跑通过一次**。两端 UI 已齐备，这条是唯一阻塞项。`make hub-init` 已自动完成「拷映射文件 + 注册 inbound 来源」，签发 token 与建 webhook 订阅仍需 Admin 后台手工。

## 仓库端页面如何访问中枢（架构约定，勿绕开）

中枢的仓库端接口用共享密钥 `X-WMS-Token` 认证，**浏览器不得持有它**。所以仓库端 3 屏不直连中枢，而是走 wms 后端代理：

```
admin 前端 → /api/admin/hub/*（同源 cookie 会话 + page_key `hub-warehouse`）
           → wms/api/routes/admin/admin_hub.py（注入 X-WMS-Token）
           → 中枢 /api/v1/warehouse/*
```

- 代理只转发**白名单内的路径形状**（精确正则，非前缀匹配），并原样透传状态码与 JSON。
- `HUB_WMS_TOKEN` **刻意复用 `WMS_API_TOKEN`**，两边不可能配错。
- 新增仓库端页面时：Hub 先加接口 → 代理白名单加路径 → 前端调 `/admin/hub/...`。

## 跨系统契约（易错点，勿重犯）

1. **`items` 入站信封 `external_id` 必须是 `sku_code`**（如 `A001-1`），**不是**中枢内部的 UUID —— sentry-wms 用它写 `cross_system_mappings.source_id`，而订单行的货号解析正是按 `sku_code` 查这张表。
2. **订单行不传 `item_id`**，传 `lines[].sku_code`，由 WMS 经 `cross_system_lookup` 解析成自己的 `item_id`。因此**货号必须先推 `items`**，否则下单返回 `409 cross_system_lookup_miss`。
3. 幂等键是 `(source_system, external_id, external_version)`，其中 `external_id` = `submission_order.external_id`（每个订单号一个）。
4. 超时提醒：后台每 5 分钟自动扫描（`TIMEOUT_SCAN_INTERVAL_SECONDS`，设 0 关闭），逻辑在 `services.scan_timeouts`。
5. **回归防线**：`backend/tests/test_adapter_contract.py` 直接读 `wms/db/mappings/hub.yaml.template` 反查适配器真实发出的 payload，映射与适配器一旦漂移即测试失败。

## 关键落地约束（设计文档得出的硬结论）

1. **货号取号必须原子**：`UPDATE category SET seq_counter = seq_counter + 1 WHERE id = ? RETURNING code_prefix || '-' || seq_counter`。不要 `SELECT MAX()+1`（并发重号）。`sku_code` 加 UNIQUE 兜底。
2. **部署**：同一 PG 实例 + 同一 database，中枢表放独立 **`hub` schema**。同库才能 FK + 同事务取号；独立 schema 让两套迁移互不干扰，将来拆库只需导出 `hub`。
3. **中枢独立进程**（建议 FastAPI），不塞进 sentry-wms 的 Flask。
4. **货号一 `active` 就必须立刻推送到 sentry-wms 的 `items`** —— 因为 sentry-wms 下单时要求 `item_id` 已存在，不能等下单才推。
5. 集成方向：中枢 → sentry-wms 走 **inbound API**（`api/routes/inbound.py`）；sentry-wms → 中枢走 **Webhook**（验签 + 按 `event_id` 去重 + 状态只向前不向后）。

## 交付物

| 文件 | 说明 |
|---|---|
| `代发仓ERP_正式设计文档_v1.2.md` | **唯一权威设计文档**（内容版本 v1.3，文件名未获授权重命名）。数据模型 / 完整状态机 / 两端页面清单 / 改造路径 / **§5.4.1 实施进展** |
| `db/` | `hub` schema 迁移（11 表 + 触发器）、占位类目 seed、结构自检 |
| `backend/` | 中枢 FastAPI（`app/`）+ 测试（`tests/`，**9 个用例**：5 端到端 + 3 入站契约 + 1 超时提醒） |
| `frontend-ops/` | 运营端 3 屏（提交 / 我的申请 / 确认） |
| `wms/` | sentry-wms 底座 + Hub 接入改造：`db/migrations/082_hub_item_master_fields.sql`、`db/mappings/hub.yaml.template`、`db/seed-hub-source.sql`、`docs/hub-integration.md` |
| `docker-compose.yml` / `Makefile` | 部署编排；`make app / wms / all / hub-init / migrate / db-check` |
| ~~`代发仓ERP_方案确认纪要_2026-09-14.md`~~ | 原始交接文档，**已被用户删除**（结论已并入设计文档） |
