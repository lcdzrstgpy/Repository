# 仓储管理系统（Warehouse ERP）

公司内部使用的轻量仓储管理系统，打通「运营出单 → 仓储履约 → 状态回传」这条协作链路。

- **后端**：FastAPI + SQLAlchemy 2.0 + Pydantic v2（Python 3.12，端口 `8000`）
- **前端**：Vue 3 + Vite + Element Plus + Pinia（端口 `5173`）
- **数据库**：MySQL 8（字符集 `utf8mb4`）
- **约定文档**：[`docs/接口契约.md`](docs/接口契约.md) —— 后端 / 前端 / 数据库三方的唯一约定，字段名与状态值不得随意更改

---

## 一、业务链路

```
运营侧                    后台订单池              仓储侧
──────                    ──────────              ──────
出单 ──────────────▶ 待接单(10) ──仓储接单──▶ 已接单(20)
                                                  │
                                             开始备货
                                                  ▼
                                             备货中(30)
                                                  │
                                               拣货发货
                                                  ▼
运营确认完成 ◀────── 状态回传 ────── 已发货(40) ──▶ 已完成(50)
```

### 订单状态流转

```
                    ┌──────────────── 已取消(90) ◀── 取消（运营/仓储）
                    │                        ▲
                    │                        │
 待接单(10) ──接单──▶ 已接单(20) ──备货──▶ 备货中(30) ──发货──▶ 已发货(40) ──确认──▶ 已完成(50)
```

| 状态值 | 状态 | 操作角色 | 说明 |
|---|---|---|---|
| 10 | 待接单 | 运营（自动进入） | 订单提交后进入后台订单池 |
| 20 | 已接单 | 仓储 | 写 `claimed_by` / `claimed_at` / `warehouse_id` |
| 30 | 备货中 | 仓储 | 写 `prepare_at` |
| 40 | 已发货 | 仓储 | 写 `shipped_at` / `express_no`，**状态回传点** |
| 50 | 已完成 | 运营 | 写 `finished_at` |
| 90 | 已取消 | 运营 / 仓储 | 仅 10 / 20 / 30 可取消，写 `cancel_reason` |

> 合法性校验见契约文档第六节，非法流转后端返回 `code = 1001`。

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
│   │   └── main.py       # 应用入口
│   ├── tests/
│   │   └── smoke_test.py # 端到端冒烟测试（254 项断言，覆盖全部接口）
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
│   ├── schema.sql        # 建库 + 19 张表 DDL（严格对应契约第四、九、十、十六、十七节）
│   └── init_data.sql     # 初始化数据（严格对应契约第七节，幂等可重复执行）
│
├── docs/                 # 项目文档
│   ├── 接口契约.md        # 接口 / 数据模型 / 状态机 / 初始化数据唯一约定
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
# 会把三个账号的密码重置为 admin123，示例订单以单号 SO202609160001 判重、不会重复插入）
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
| `admin` | 管理员 | `admin` | 全部权限：基础数据增删改、全部订单可见、库存查询 |
| `operator1` | 运营小王 | `operator` | 创建订单、**只能看自己创建的订单**、取消自己的订单、确认完成 |
| `warehouse1` | 仓管老李 | `warehouse` | 待接单列表（全部订单）、接单、备货、发货、库存查询 |

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
| 库存查询 / 库存流水 | ✅ | ✅ | ✅ | ❌ |
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

项目自带一个端到端冒烟测试，**真实启动 FastAPI 应用**并把契约里的接口全部跑一遍
（路由 → 依赖注入 → Pydantic 校验 → SQLAlchemy 事务 → 序列化 → 统一响应），
覆盖订单主链路、库存、出库单、采购、预留与缺货拦截、移库、盘点、库存预警、
Excel 导入导出、角色权限矩阵，共 **254 项断言**。

```bash
cd backend
python3 -m pip install -r requirements.txt httpx
python3 tests/smoke_test.py
```

- **默认使用临时 SQLite 文件库，不会碰你的 MySQL**，跑完自动删除
- 全部通过时退出码为 0，输出末尾打印 `总计 N 项断言：通过 N，失败 0`
- 失败时会打印每条的期望值与实际值，便于定位
- `SMOKE_DB=/path/to.db` 可指定库文件；`SMOKE_KEEP=1` 保留库文件以便排查

**两点测试环境的适配（不影响生产代码）**

1. `app/models` 里用了 MySQL 方言的 `TINYINT`，SQLite 渲染不了 DDL —— 脚本在导入 app 之前把它换成 `SmallInteger`
2. 主键是 `BigInteger`，而 SQLite 只有 `INTEGER PRIMARY KEY` 才自增 —— 脚本只把**主键列**降级为 `Integer`

> ⚠️ **测试的局限**：`SELECT ... FOR UPDATE` 在 SQLite 上会被方言静默省略（行锁退化为无锁）。
> 因此冒烟测试验证的是**逻辑正确性**，**不是 MySQL 下的并发行为**。并发相关的正确性
> 依赖代码审查（行锁是否落在正确的读路径上）与 MySQL 环境下的实际压测。

---

## 十一、相关文档

- [`docs/依赖与启动.md`](docs/依赖与启动.md) —— **依赖清单 + 三种启动方式**（含无 MySQL 的 SQLite 开发模式）+ 排障
- [`docs/接口契约.md`](docs/接口契约.md) —— 接口、数据模型、状态机、初始化数据（**前后端与数据库的唯一约定**）
- [`docs/组合抄方案.md`](docs/组合抄方案.md) —— 技术选型与方案背景
- [`backend/tests/smoke_test.py`](backend/tests/smoke_test.py) —— 端到端冒烟测试（53 项断言，**不需要 MySQL**，改完代码可随时回归）
