# 仓储管理系统（Warehouse ERP）

公司内部使用的轻量仓储管理系统，打通「运营出单 → 仓储履约 → 状态回传」这条协作链路。

> **固定 Python 环境**：后端开发、依赖安装和测试统一使用 Conda 环境 `cangchu`（Python 3.12.14）。
>
> ```bash
> conda activate cangchu
> cd backend
> python -m pip install -r requirements.txt
> python tests/smoke_test.py
> ```
>
> 解释器路径：`/Applications/anaconda3/envs/cangchu/bin/python`。请勿使用 `base` 或其他 Python 环境执行后端命令。

- **后端**：FastAPI + SQLAlchemy 2.0 + Pydantic v2（Python 3.12，端口 `8000`）
- **前端**：Vue 3 + Vite + Element Plus + Pinia（端口 `5173`）
- **数据库**：MySQL 8（字符集 `utf8mb4`）
- **约定文档**：[`docs/接口契约.md`](docs/接口契约.md) —— 后端 / 前端 / 数据库三方的唯一约定，字段名与状态值不得随意更改

---

## 〇、交接说明（新接手请先读这一节）

### 项目现状

| 项 | 状态 |
|---|---|
| 代码 | 功能已实现，端到端冒烟测试 **68 项全部通过** |
| 运行验证 | 已在本地跑通完整业务链路（用 SQLite 顶替 MySQL） |
| 生产部署 | **未部署**，Ubuntu 部署方案待落地 |
| 代码托管 | GitHub `lcdzrstgpy/Repository` 的 `warehouse-erp` 分支 |

**规模**：后端 44 个文件 / 约 6,400 行 Python；前端 61 个文件 / 约 9,700 行 Vue + JS。

### 分工边界（重要）

**本仓库负责「数据流转」** —— 订单状态机、货号关联、库存变更、采购链路这些流程性的部分。

以下模块**由其他同事负责**，本仓库未实现或只做了最小实现，接手时注意别重复造：

- **库存管理**（库位、批次、保质期、库存预警的完整实现）
- **货号管理**（货号的完整生命周期、与外部系统的同步）

### 已知问题

1. **新建货号后，库存列表里看不到它** —— 新建 SKU 时只创建了 `ProductSku` 记录，**没有在 `inventory` 表建对应的库存行**。库存列表是从 `inventory` 表查的，没行就不显示（而不是显示 0）。属于库存管理范畴，**未处理**。
2. **SQLite 下并发防护失效** —— 开发模式用 SQLite 时 `SELECT ... FOR UPDATE` 会被静默忽略，行锁不生效。**生产必须用 MySQL**。
3. **`prepare` 接口已废弃** —— 保留路由避免前端 404，但调用返回 `code=1001`。新流程走 `confirm-quantity`。
4. **`approver` 角色没有初始化账号** —— 契约里定义了这个角色（用于采购审批），但 `init_data` 没建对应用户，目前采购审批只能用 `admin`。

### 待办

- [ ] Ubuntu 生产部署（nginx + systemd + MySQL）。生产环境**必须改**：`JWT_SECRET_KEY`、默认密码、`CORS_ORIGINS`
- [ ] 库存管理、货号管理（其他同事负责）
- [ ] 消息通知（订单状态变更提醒）
- [ ] 生产环境并发压测（SQLite 测不了，需要 MySQL）

### 接手后怎么快速上手

1. 读本文档的 **「一、业务链路」** 了解流程
2. 读 **[`docs/接口契约.md`](docs/接口契约.md)** —— 前后端与数据库的唯一约定，改代码前必看
3. 按 **「四、快速开始」** 把服务跑起来
4. 跑 **`backend/tests/smoke_test.py`**（68 项断言，不需要 MySQL）确认环境没问题
5. 改完代码**务必重跑一次冒烟测试** —— 它能拦住大部分低级错误

---

## 一、业务链路

```
运营侧                                仓储侧
──────                                ──────
录入订单                              接单
（订单号 + 多行商品：                    │
  商品名 + 货号或勾选新品      ──▶    逐行处理货号：
  + 数量 + 预计成本）                    · 填了货号 → 匹配系统里的 SKU 并关联
  │                                    · 勾了新品 → 新建货号并关联
  │ 提交前弹窗二次确认数量               │
  │                              （全部关联完成才能继续）
  │                                    ▼
  │                                 按数量查库存
  │                                    ├─ 够   → 发货
  │                                    └─ 不够 → 采购 → 入库 → 发货
  │                                    │
  ◀──────────── 状态回传 ───────────────┘
  │
确认完成
```

### 三条硬规则

1. **货号与新品二选一** —— 每个订单行必须「填了货号」或「勾选新品」，不能都填也不能都不填
2. **关联后锁定** —— 订单行的货号一旦由仓库关联成功，运营端不可再修改
3. **采购价上限** —— 因某订单缺货而发起的采购，采购单价**不得高于**该订单行运营填写的**预计成本**

### 订单状态流转

```
                    ┌──────────────── 已取消(90) ◀── 取消（运营/仓储）
                    │                        ▲
                    │                        │
 待接单(10) ──接单──▶ 已接单(20) ──绑完货号──▶ 数量待确认(25) ──运营确认──▶ 备货中(30) ──发货──▶ 已发货(40) ──确认──▶ 已完成(50)
                      （系统自动）              （系统自动，同时预留库存）
```

| 状态值 | 状态 | 谁触发 | 说明 |
|---|---|---|---|
| 10 | 待接单 | 运营下单 | 订单进入后台订单池 |
| 20 | 已接单 | 仓储接单 | 写 `claimed_by` / `claimed_at` / `warehouse_id`；**此阶段处理货号关联** |
| 25 | 数量待确认 | 系统自动（仓储绑完所有货号） | 等运营确认数量 |
| 30 | 备货中 | 系统自动（运营确认数量） | 写 `prepare_at`；仓储备货或采购，尚不扣减/预留库存 |
| 40 | 已发货 | 仓储发货 | 写 `shipped_at` / `express_no`，**状态回传点** |
| 50 | 已完成 | 运营确认 | 写 `finished_at` |
| 90 | 已取消 | 运营 / 仓储 | 仅 10 / 20 / 25 / 30 可取消，写 `cancel_reason` |

> 合法性校验见契约文档第六节与第十八章，非法流转后端返回 `code = 1001`。
> 运营确认数量不校验库存；库存不足由仓储在备货阶段采购处理，实际发货时才校验并扣减库存。
> 原 `POST /api/warehouse/orders/{id}/prepare` **已废弃**（保留路由但返回 1001），备货改由运营确认数量触发。

---

## 二、目录结构

```
仓储管理erp2/
├── backend/              # 后端服务（FastAPI + SQLAlchemy）
│   ├── app/
│   │   ├── api/          # 路由：auth / basic / order / warehouse / inventory / stock / purchase / ops / data_io
│   │   ├── core/         # 配置、数据库连接、统一响应、安全（JWT）
│   │   ├── models/       # ORM 模型（user / basic / order / inventory / stock / purchase / ops）
│   │   ├── schemas/      # Pydantic 校验与序列化模型
│   │   ├── services/     # 库存服务（change_inventory / reserve_inventory / release_inventory）
│   │   └── main.py       # 应用入口
│   ├── tests/
│   │   └── smoke_test.py # 端到端冒烟测试（68 项断言，不需要 MySQL）
│   ├── create_tables.py  # 按 ORM 模型建表
│   ├── init_data.py      # 写入初始化数据（含 bcrypt 密码哈希生成）
│   ├── requirements.txt  # 依赖清单
│   └── .env.example      # 环境变量样例
│
├── frontend/             # 前端工程（Vue 3 + Vite + Element Plus）
│   ├── src/              # 页面、组件、路由、状态管理、请求封装
│   ├── vite.config.js    # 含 /api → http://localhost:8000 代理
│   └── package.json
│
├── sql/                  # 数据库脚本
│   ├── schema.sql        # 建库 + 19 张表 DDL（唯一真源）
│   └── init_data.sql     # 初始化数据（幂等可重复执行）
│
├── docs/                 # 项目文档
│   ├── 依赖与启动.md      # 依赖清单 + 三种启动方式 + 排障
│   ├── 接口契约.md        # 接口 / 数据模型 / 状态机 / 初始化数据（唯一约定）
│   └── 组合抄方案.md      # 技术选型与方案背景
│
├── docker-compose.yml    # MySQL 8 容器编排（自动执行 sql/ 下脚本）
├── .gitignore
└── README.md
```

---

## 三、环境要求

| 依赖 | 版本要求 | 说明 |
|---|---|---|
| Python | 3.12+ | 后端运行环境 |
| Node.js | 18+ | 前端构建环境（建议 18 LTS 或 20 LTS） |
| MySQL | 8.0 | 可用 Docker 代替本地安装 |
| Docker / Docker Compose | 最新版 | 可选，用于一键启动数据库 |

---

## 四、快速开始

### 步骤 1 · 启动数据库

**方式 A：Docker（推荐）**

```bash
# 在项目根目录执行
docker compose up -d

# 查看容器状态，等待 healthy
docker compose ps

# 查看初始化日志（确认 01-schema.sql / 02-init-data.sql 已执行）
docker compose logs -f warehouse-mysql
```

容器首次启动时会自动按顺序执行 `sql/schema.sql`（建库建表）和 `sql/init_data.sql`（初始化数据）。

**方式 B：本地 MySQL 手动执行**

```bash
# 建库建表
mysql -uroot -proot < sql/schema.sql

# 写入初始化数据
mysql -uroot -proot < sql/init_data.sql
```

> 若本地 root 密码不是 `root`，请相应调整命令与后端 `.env` 中的 `DATABASE_URL`。

### 步骤 2 · 启动后端

```bash
cd backend

# 创建并激活虚拟环境
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt

# 配置环境变量
cp .env.example .env
# 按需修改 .env，默认数据库连接为 root/root@localhost:3306/warehouse_erp

# 建表（二选一，两条路径产物不同，请只选一条）
#   路径 A（推荐）：走 Docker（步骤 1）自动执行 sql/schema.sql，或手动执行
#                   mysql -uroot -proot < sql/schema.sql
#                   —— 这是唯一真源，含全部索引，不含外键约束
#   路径 B（仅供本地快速开发）：python create_tables.py
#                   —— 由 ORM 生成，会额外带外键约束，但缺少 schema.sql 里声明的部分索引
# 如果已经走了路径 A，跳过下面这行
python create_tables.py

# 写入初始化数据（幂等，可重复执行；已执行过 init_data.sql 也可运行，
# 会把三个账号的密码重置为 admin123，示例订单以单号 TB20260917001 判重、不会重复插入）
python init_data.py

# 启动服务
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 步骤 3 · 启动前端

```bash
cd frontend

npm install
npm run dev
```

### 步骤 4 · 访问地址

| 服务 | 地址 |
|---|---|
| 前端页面 | http://localhost:5173 |
| 后端接口文档（Swagger UI） | http://localhost:8000/docs |
| 后端健康检查 | http://localhost:8000/ |

---

## 五、默认账号

密码统一为 `admin123`。

| 用户名 | 姓名 | 角色 | 权限说明 |
|---|---|---|---|
| `admin` | 管理员 | `admin` | 全部权限：基础数据增删改、全部订单可见、库存查询与调整、采购审批 |
| `operator1` | 运营小王 | `operator` | 创建订单、**只能看自己创建的订单**、取消自己的订单、确认数量、确认完成 |
| `warehouse1` | 仓管老李 | `warehouse` | 待接单列表（全部订单）、接单、关联货号、发货、库存查询、采购单 |

> **`approver`（审批）角色没有初始化账号** —— 契约里定义了这个角色用于采购单审批，但初始化数据没建对应用户，目前采购审批只能用 `admin` 操作。如果需要独立审批岗，在 `sql/init_data.sql` 和 `backend/init_data.py` 里补一个 `role = 'approver'` 的用户即可。

> ⚠️ 初始化脚本中的 bcrypt 哈希为演示用固定值，对应明文密码 `admin123`（已用 `bcrypt.checkpw` 实测校验通过）。
> 需要重置密码时执行 `cd backend && python init_data.py`：脚本对用户采用 **upsert** 语义，
> 已存在的用户也会被覆盖 `password_hash`（同步 `real_name` / `role` / `status`），
> 执行后三个账号的密码都会回到 `admin123`。**生产环境请务必修改默认密码。**

---

## 六、角色权限对照表

| 功能 | admin | operator | warehouse | approver |
|---|:---:|:---:|:---:|:---:|
| 基础数据（仓库/商品/SKU/往来单位/用户）增删改 | ✅ | ❌ | ❌ | ❌ |
| 基础数据只读查询 | ✅ | ✅ | ✅ | ✅ |
| 创建销售订单 | ✅ | ✅ | ❌ | ❌ |
| 查看订单列表 | 全部 | 仅自己创建的 | 全部 | ❌ |
| 取消订单 | ✅（10/20/30） | ✅（仅自己的，10/20/30） | ✅（10/20/30） | ❌ |
| 待接单列表 | ✅ | ❌ | ✅ | ❌ |
| 接单 → 已接单 | ✅ | ❌ | ✅ | ❌ |
| 开始备货 → 备货中 | ✅ | ❌ | ✅ | ❌ |
| 发货 → 已发货 | ✅ | ❌ | ✅ | ❌ |
| 确认完成 → 已完成 | ✅ | ✅（仅自己的订单） | ❌ | ❌ |
| 货号及库存查询（只读聚合） | ✅ | ✅ | ✅ | ❌ |
| 仓储库存查询 / 库存流水 / 库存预警 | ✅ | ❌ | ✅ | ❌ |
| 库存调整（单点） | ✅ | ❌ | ❌ | ❌ |
| 移库单（建单/执行/作废） | ✅ | ❌ | ✅ | ❌ |
| 盘点单（建单/录入/完成/作废） | ✅ | ❌ | ✅ | ❌ |
| 库存预警查询 | ✅ | ✅ | ✅ | ❌ |
| SKU 安全库存维护 | ✅ | ❌ | ❌ | ❌ |
| 出库单 | ✅ | ❌ | ✅ | ❌ |
| 采购单创建/取消/收货 | ✅ | ❌ | ✅ | ❌ |
| 采购单审批 | ✅ | ❌ | ❌ | ✅ |
| 采购单列表/详情 | ✅ | ❌ | ✅ | ✅ |
| 导出商品 / SKU | ✅ | ❌ | ❌ | ❌ |
| 导出库存 | ✅ | ❌ | ✅ | ❌ |
| 导出订单 | ✅ | ✅（仅自己的） | ✅ | ❌ |
| 导入商品 | ✅ | ❌ | ❌ | ❌ |
| 单据打印 | ✅ | ✅ | ✅ | ✅ |

---

## 七、数据库表一览（19 张）

**基础数据**

| 表名 | 说明 |
|---|---|
| `sys_user` | 系统用户（含角色、bcrypt 密码） |
| `warehouse` | 仓库 |
| `product` | 商品 |
| `product_sku` | 商品 SKU（含售价、安全库存 `min_stock`） |
| `partner` | 往来单位（`type`：1 客户 / 2 供应商 / 3 两者） |

**订单与库存**

| 表名 | 说明 |
|---|---|
| `sales_order` | 销售订单主表（存汇总、状态机、接单/发货时间） |
| `sales_order_item` | 销售订单明细（`out_count` 支持部分发货） |
| `inventory` | 库存余额（唯一键 `sku_id + warehouse_id`） |
| `inventory_history` | 库存流水（每笔变动记 `before_quantity` / `after_quantity`，可追溯） |

**出库（二阶段）**

| 表名 | 说明 |
|---|---|
| `sales_out` | 出库单（发货时自动生成，作为发货凭证） |
| `sales_out_item` | 出库单明细 |

**采购（三阶段）**

| 表名 | 说明 |
|---|---|
| `purchase_order` | 采购单（`status`：10 待审批 / 20 已审批 / 30 已入库 / 90 已取消） |
| `purchase_order_item` | 采购单明细（`in_count` 支持部分入库） |
| `purchase_in` | 采购入库单（收货时生成，**此时才增加库存**） |
| `purchase_in_item` | 采购入库单明细 |

**移库与盘点（五阶段）**

| 表名 | 说明 |
|---|---|
| `stock_transfer` | 移库单（`status`：10 草稿 / 20 已完成 / 90 已作废） |
| `stock_transfer_item` | 移库单明细 |
| `stock_take` | 盘点单（`status`：10 盘点中 / 20 已完成 / 90 已作废，含账面快照与差异合计） |
| `stock_take_item` | 盘点单明细（账面 / 实盘 / 差异） |

---

## 八、采购流程与库存变更

**采购链路**

```
库存不足 → 创建采购单(10 待审批) → 审批(20 已审批) → 收货入库(30 已入库) → 库存增加 → 订单继续备货
```

关键设计：**采购单本身不影响库存**，只有「收货入库」才增加库存。订单类操作与库存类操作严格分离（抄 yudao ERP 的设计）。

**所有库存变动统一走一个入口**

后端 `app/services/inventory_service.py` 的 `change_inventory()` 是唯一的库存变更入口，业务代码禁止直接 UPDATE 库存表。它实现了：

1. **去重合并** —— 同一 `(sku_id, warehouse_id)` 的多行先合并，减少数据库交互
2. **懒创建** —— 库存行不存在时直接 INSERT，用 savepoint 兜住并发冲突（不"先查后插"）
3. **批量悲观锁** —— 一次性 `SELECT ... FOR UPDATE` 锁定所有待变更行，**不在循环里逐行加锁**（避免死锁）
4. **校验** —— 出库时校验可用量，不足则报错并带出 SKU 编码、仓库名、可用量、需求量
5. **写流水** —— 每次变动都写 `inventory_history`，记变动前后数量

**库存变动类型**

| `order_type` | 中文 | 触发场景 |
|---|---|---|
| `SALES_OUT` | 销售出库 | 订单发货 |
| `PURCHASE_IN` | 采购入库 | 采购收货 |
| `ADJUST` | 库存调整 | 管理员手动单点调整（盘点） |
| `TRANSFER_OUT` | 移库出 | 执行移库时出库仓扣减 |
| `TRANSFER_IN` | 移库入 | 执行移库时入库仓增加 |
| `STOCK_TAKE` | 盘点调整 | 完成盘点时按差异调整 |

---

## 八之二、移库、盘点与库存预警（五阶段）

> 这三块都是「抄」来的：移库单抄 yudao WMS 的 `wms_transfer` + 若依WMS 的「移库」，
> 盘点单抄 yudao WMS 的 `wms_stock_take` + 若依WMS 的「盘库」，
> 库存预警抄 `vvsgxmn/WarehouseManage` 的安全库存预警。
> 三者都**没有新增库存变更路径**，一律复用 `change_inventory()`。

**移库链路**

```
建单(草稿,10) ──执行移库──▶ 出库仓 -N / 入库仓 +N ──▶ 已完成(20)
                            （TRANSFER_OUT + TRANSFER_IN 两条流水）
草稿 ──作废──▶ 已作废(90)（不动库存）
```

关键设计：**建单不动库存，只有「执行移库」才动**（与采购单同样的「单据与库存分离」）。
出库仓库存不足时整体失败并回滚，不会出现「扣了出库仓没加入库仓」。

并发保护分两层：先锁移库单行（防重复执行），再按**全局有序顺序预锁定出库仓 + 入库仓的全部库存行**
（`lock_inventory_keys`）。否则两张方向相反的移库单（A→B 与 B→A）并发执行时，
两次 `change_inventory` 各自的加锁顺序可能相反，形成 ABBA 死锁（InnoDB 1213）。

**盘点链路**

```
建单(盘点中,10，快照账面) ──录入实盘──▶ ──完成盘点──▶ 按差异调库存 ──▶ 已完成(20)
                                                      （STOCK_TAKE 流水）
盘点中 ──作废──▶ 已作废(90)（不动库存）
```

- 建单时选定仓库 + SKU 清单（不传 `sku_ids` 则取该仓库全部有库存记录的 SKU），**自动快照账面数量**
- 前端「完成盘点」会**先落盘未保存的实盘编辑**，再弹确认框、再完成——避免用户刚改的数字被静默丢弃
- 与 `POST /api/inventory/adjust` 的关系：`adjust` 是**单点即时调整**（无单据），
  盘点单是**成批、有单据留痕**的流程。两者都走 `change_inventory`，互不替代。
- 账面快照与完成时的实际库存可能不一致（盘点期间发生了出入库）。约定：以快照账面为基准算差异并落流水，
  `diff_count` 记录该次盘点的差异合计，不做二次校验。

**库存预警**

- `product_sku.min_stock` 是安全库存下限，**0 表示不预警**
- `GET /api/inventory/alerts` 返回 `min_stock > 0 且 可用量 < min_stock` 的行，按短缺量从大到小排序，
  每行额外带 `min_stock` 与 `shortage`（短缺量）
- 可用量定义沿用第十二节：`available_quantity = quantity - reserved_quantity`

---

## 九、常见问题

### 1. 端口被占用怎么办？

**查看占用进程**

```bash
# 8000 后端端口
lsof -i :8000

# 5173 前端端口
lsof -i :5173

# 3306 数据库端口
lsof -i :3306
```

**处理方式**

```bash
# 杀掉占用进程（将 PID 替换为实际进程号）
kill -9 <PID>

# 或改用其他端口启动后端
uvicorn app.main:app --reload --port 8001
```

> 若后端换端口，记得同步修改 `frontend/vite.config.js` 中 `/api` 代理的目标地址。

### 2. MySQL 连接失败怎么排查？

按以下顺序逐项确认：

1. **容器是否在运行**
   ```bash
   docker compose ps
   docker compose logs -f warehouse-mysql
   ```
2. **端口是否被本地 MySQL 占用**
   ```bash
   lsof -i :3306
   ```
   若本地已有 MySQL 在跑，可把 `docker-compose.yml` 中的端口映射改为 `"3307:3306"`，
   并同步修改后端 `.env` 的 `DATABASE_URL` 端口。
3. **连接串是否正确** —— 默认应为：
   ```
   DATABASE_URL=mysql+pymysql://root:root@localhost:3306/warehouse_erp?charset=utf8mb4
   ```
4. **库和表是否已建**
   ```bash
   docker exec -it warehouse-mysql mysql -uroot -proot -e "USE warehouse_erp; SHOW TABLES;"
   ```
   应当看到 19 张表（数量不对说明 schema.sql 没执行完整）。
5. **数据卷残留导致初始化脚本未执行** —— 初始化脚本只在数据卷为空时执行一次：
   ```bash
   docker compose down -v      # ⚠ 会删除数据，请先确认无需保留
   docker compose up -d
   ```
6. **认证插件问题**（MySQL 8 默认 `caching_sha2_password`）：
   compose 已加 `--default-authentication-plugin=mysql_native_password`，
   若仍报认证错误，可手动执行：
   ```sql
   ALTER USER 'root'@'%' IDENTIFIED WITH mysql_native_password BY 'root';
   FLUSH PRIVILEGES;
   ```

### 3. `npm install` 慢怎么换源？

```bash
# 临时使用（单次生效）
npm install --registry=https://registry.npmmirror.com

# 永久切换
npm config set registry https://registry.npmmirror.com

# 查看当前源
npm config get registry
```

Python 依赖同理，可临时指定国内源：

```bash
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

### 4. 前端请求接口报 CORS 错误？

确认后端 `.env` 中的 `CORS_ORIGINS` 包含前端地址（默认 `http://localhost:5173`），
且前端通过 Vite 代理访问 `/api`（见 `frontend/vite.config.js`）。

### 5. 登录提示密码错误？

初始化数据中的哈希固定对应密码 `admin123`。若仍失败，用后端脚本重新生成（脚本会**覆盖已存在用户的密码**）：

```bash
cd backend
source .venv/bin/activate
python init_data.py
```

该脚本对用户采用 upsert 语义：已存在的用户不再被跳过，`password_hash` 会被覆盖，
并同步 `real_name` / `role` / `status`。执行后 `admin`、`operator1`、`warehouse1`
的密码均重置为 `admin123`，且脚本可重复执行、不会产生重复数据。

---

## 十、如何验证后端是好的（端到端冒烟测试）

项目自带一个端到端冒烟测试 `backend/tests/smoke_test.py`，**真实加载 FastAPI 应用**并打接口
（路由 → 依赖注入 → Pydantic 校验 → SQLAlchemy 事务 → 序列化 → 统一响应），
共 **76 项断言**，覆盖：

- 认证（登录成功 / 密码错误 / 无 token）
- 基础数据 CRUD 与筛选（`partner.type` / `user.role`）
- 运营侧货号与只读库存查询（运营不可访问仓储库存操作台）
- 运营下单（订单号唯一、**货号与新品二选一校验**、总额后端计算）
- 仓储接单 → 绑定货号（关联已有 + 新建）→ **关联后锁定**
- **数量待确认 → 运营填写并确认数量 → 仓储备货/采购**
- 发货实扣、出库单生成、库存流水
- 状态回传与确认完成、状态机拦截
- 权限矩阵（403）
- 库存不足拦截、**采购限价校验**
- 采购全链路（创建 → 审批 → 收货入库）
- Excel 导出

```bash
cd backend
python tests/smoke_test.py
```

- **不需要 MySQL，也不需要先启动后端** —— 脚本自己建库、灌初始化数据，用 TestClient 直接打接口
- 每次运行都会重建 `backend/smoke_test.db`（已在 `.gitignore` 中忽略）
- 全部通过时末尾输出 `通过 68 项，失败 0 项`
- 失败时会逐条打印期望值与实际值，便于定位

**为什么能在 SQLite 上跑**（两处适配，不影响生产代码）

1. `app/models` 用了 MySQL 方言的 `TINYINT`，SQLite 渲染不了 DDL —— 脚本给 SQLite 方言注册了 `TINYINT` 的编译规则
2. 主键是 `BigInteger`，而 SQLite 只有 `INTEGER PRIMARY KEY` 才自增 —— 脚本同样注册了 `BigInteger` 的编译规则

> ⚠️ **测试的局限**：`SELECT ... FOR UPDATE` 在 SQLite 上会被方言静默省略（行锁退化为无锁）。
> 因此冒烟测试验证的是**逻辑正确性**，**不是 MySQL 下的并发行为**。
> 并发相关的正确性依赖代码审查与 MySQL 环境下的实际压测。

> 💡 **改完代码务必重跑一次。** 它能拦住 `compileall` 查不出来的问题 ——
> 比如某次改动删掉了 `check_available` 的导入但函数里还在用，语法检查通过、一跑就 500。

---

## 十一、相关文档

- [`docs/依赖与启动.md`](docs/依赖与启动.md) —— **依赖清单 + 三种启动方式**（含无 MySQL 的 SQLite 开发模式）+ 排障
- [`docs/接口契约.md`](docs/接口契约.md) —— 接口、数据模型、状态机、初始化数据（**前后端与数据库的唯一约定**）
- [`docs/组合抄方案.md`](docs/组合抄方案.md) —— 技术选型与方案背景
- [`backend/tests/smoke_test.py`](backend/tests/smoke_test.py) —— 端到端冒烟测试（53 项断言，**不需要 MySQL**，改完代码可随时回归）
