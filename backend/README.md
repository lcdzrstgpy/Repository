# 仓储管理系统 · 后端（一阶段）

公司内部仓储管理系统后端服务。本阶段跑通**订单主链路**：
运营下单 → 订单进入订单池 → 仓储接单 → 备货 → 发货即完成。

> 一阶段**不实现**库存扣减与采购逻辑；`inventory` / `inventory_history` 表已建好，库存查询接口只读。

字段名、状态值、接口路径、响应格式全部以 `docs/接口契约.md` 为准。

---

## 一、环境要求

| 项 | 版本 |
|---|---|
| Python | 3.12+（本项目在 3.13.12 上验证） |
| MySQL | 8.0 |
| 后端端口 | 8000 |
| 前端端口 | 5173 |

---

## 二、安装依赖

```bash
cd backend

# 建议使用虚拟环境
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

pip install -r requirements.txt
```

依赖清单（`requirements.txt`）：FastAPI、Uvicorn、SQLAlchemy 2.0、Pydantic v2、PyMySQL、
python-jose[cryptography]、passlib[bcrypt]、python-dotenv。

---

## 三、配置

```bash
cp .env.example .env
```

`.env` 关键项：

| 变量 | 默认值 | 说明 |
|---|---|---|
| `DATABASE_URL` | `mysql+pymysql://root:root@localhost:3306/warehouse_erp?charset=utf8mb4` | 数据库连接串 |
| `JWT_SECRET_KEY` | `warehouse-erp-secret-key-change-me` | **生产环境必须替换** |
| `JWT_EXPIRE_DAYS` | `7` | token 有效期（天） |
| `CORS_ORIGINS` | `http://localhost:5173` | 允许的前端地址，逗号分隔 |
| `DEBUG` | `true` | 为 true 时 500 错误会带上异常详情 |

未创建 `.env` 时，全部配置使用上述默认值，可直接启动。

---

## 四、初始化数据库

```bash
# 1. 建库 + 建表（不使用 Alembic，直接由模型驱动）
python3 create_tables.py

# 2. 写入初始化数据（幂等，可重复执行）
python3 init_data.py
```

`create_tables.py` 会自动 `CREATE DATABASE IF NOT EXISTS warehouse_erp`，再执行
`Base.metadata.create_all()`，共创建 9 张表：

`sys_user`、`warehouse`、`product`、`product_sku`、`partner`、
`sales_order`、`sales_order_item`、`inventory`、`inventory_history`

`init_data.py` 写入的初始数据（契约第七节）：

| 类别 | 内容 |
|---|---|
| 用户 | `admin` / 管理员、`operator1` / 运营小王、`warehouse1` / 仓管老李，密码统一 `admin123`（bcrypt 存储） |
| 仓库 | `WH001` 主仓、`WH002` 备用仓 |
| 商品 | 3 个商品，各 1 个 SKU：`SKU001` ~ `SKU003` |
| 往来单位 | 2 个客户（type=1）、2 个供应商（type=2） |
| 库存 | 主仓为 3 个 SKU 各写入 `quantity = 100` |
| 示例订单 | 1 条 `status = 10` 的待接单订单，含 2 条明细（合计 15 件 / 342.50 元） |

---

## 五、启动服务

```bash
cd backend
python3 -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

- 接口文档（Swagger UI）：<http://localhost:8000/docs>
- 备用文档（ReDoc）：<http://localhost:8000/redoc>

联调前先用 `admin / admin123` 调 `POST /api/auth/login` 拿 token，在 Swagger 右上角
`Authorize` 里填入即可。

---

## 六、接口清单

除 `POST /api/auth/login` 外，**所有接口**需请求头 `Authorization: Bearer <token>`。

### 认证 `/api/auth`

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/auth/login` | 登录，返回 `access_token` / `token_type` / `user` |
| GET | `/api/auth/me` | 当前登录用户 |
| POST | `/api/auth/logout` | 登出（JWT 无状态，前端清 token 即可） |

### 基础数据

以下五组接口结构完全一致，**仅 admin 可写，其他角色只读**：

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/warehouses` | 列表 `?page=&page_size=&keyword=` |
| GET | `/api/warehouses/{id}` | 详情 |
| POST | `/api/warehouses` | 新增 |
| PUT | `/api/warehouses/{id}` | 修改 |
| DELETE | `/api/warehouses/{id}` | 删除（软删，置 `status=0`） |

同样结构替换路径：`/api/products`、`/api/skus`、`/api/partners`、`/api/users`。
其中 `/api/users` **仅 admin 可访问全部方法**。

下拉选项：

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/partners/options?type=1` | 返回 `[{id, name}]`，type 可选 |
| GET | `/api/skus/options` | 返回 `[{id, sku_code, name, spec, price}]` |
| GET | `/api/warehouses/options` | 返回 `[{id, name}]` |

### 运营侧 · 订单 `/api/sales-orders`

| 方法 | 路径 | 说明 | 角色 |
|---|---|---|---|
| POST | `/api/sales-orders` | 创建订单 | operator / admin |
| GET | `/api/sales-orders` | 订单列表 | 全部（可见性见下） |
| GET | `/api/sales-orders/{id}` | 订单详情（含明细） | 全部（可见性见下） |
| POST | `/api/sales-orders/{id}/cancel` | 取消订单 | operator（本人）/ warehouse / admin |

**可见性规则**：`operator` 只返回 `created_by = 当前用户` 的订单；`admin`、`warehouse` 返回全部。

### 仓储侧 · 订单处理 `/api/warehouse`

| 方法 | 路径 | 说明 | 角色 |
|---|---|---|---|
| GET | `/api/warehouse/pending-orders` | 待接单列表（`status=10` 全部订单） | warehouse / admin |
| POST | `/api/warehouse/orders/{id}/claim` | 接单，body `{"warehouse_id": 1}` | warehouse / admin |
| POST | `/api/warehouse/orders/{id}/prepare` | 开始备货 | warehouse / admin |
| POST | `/api/warehouse/orders/{id}/ship` | 发货，body `{"express_no": "..."}` | warehouse / admin |

### 库存查询（只读）

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/inventory` | 库存列表 `?page=&page_size=&warehouse_id=&keyword=` |
| GET | `/api/inventory/history` | 库存流水 `?page=&page_size=&sku_id=&warehouse_id=` |

---

## 七、统一响应与错误码

所有接口（含错误）统一返回：

```json
{ "code": 0, "msg": "ok", "data": {} }
```

| code | 含义 |
|---|---|
| 0 | 成功 |
| 400 | 参数错误 |
| 401 | 未登录 / token 失效 |
| 403 | 无权限 |
| 404 | 资源不存在 |
| 500 | 服务器内部错误 |
| 1001 | 业务错误（如状态流转不合法），`msg` 为具体原因 |

分页响应 `data` 结构：`{ "list": [], "total": 100, "page": 1, "page_size": 20 }`。

> **注意**：为保证响应体格式统一，业务码放在 `body.code`，HTTP 状态码固定为 `200`。
> 前端 axios 拦截器判断 `res.data.code !== 0` 即可。

---

## 八、订单状态机

```
待接单(10) --仓储接单--> 已接单(20) --开始备货--> 备货中(30) --发货--> 已完成(50)
     |                       |                      |
     +-----------------------+----------------------+--取消--> 已取消(90)
```

| 操作 | 允许的当前状态 | 目标状态 | 允许角色 |
|---|---|---|---|
| 接单 | 10 | 20 | warehouse / admin |
| 备货 | 20 | 30 | warehouse / admin |
| 发货 | 30 | 50 | warehouse / admin |
| 取消 | 10 / 20 / 25 / 30 | 90 | operator（本人）/ warehouse / admin |

流转不合法时返回 `code = 1001`，`msg` 会带上当前状态中文名，例如：

```json
{ "code": 1001, "msg": "订单当前状态为「已接单」，无法执行接单操作", "data": null }
```

---

## 九、目录结构

```
backend/
├── app/
│   ├── main.py            # FastAPI 实例、CORS、路由注册、全局异常处理
│   ├── core/
│   │   ├── config.py      # 配置，读 .env
│   │   ├── database.py    # engine / SessionLocal / Base / get_db
│   │   ├── security.py    # JWT、bcrypt、get_current_user、require_roles
│   │   └── response.py    # 统一响应体 + 业务异常
│   ├── models/            # SQLAlchemy 2.0 模型
│   ├── schemas/           # Pydantic v2 请求模型 + 响应序列化器
│   └── api/               # auth / basic / order / warehouse / inventory
├── create_tables.py       # 建库建表
├── init_data.py           # 初始化数据（幂等）
├── requirements.txt
├── .env.example
└── README.md
```

---

## 十、常见问题

**Q：`create_tables.py` 报连接失败？**
确认 MySQL 已启动、`.env` 中 `DATABASE_URL` 的账号密码正确，且该账号有建库权限。

**Q：登录报 500，日志里是 bcrypt 相关报错？**
`requirements.txt` 已把 `bcrypt` 固定在 `4.0.1`（4.1+ 移除了 passlib 1.7.4 依赖的属性）。
如本地已有更高版本：`pip install "bcrypt==4.0.1" --force-reinstall`。

**Q：前端跨域？**
确认 `.env` 的 `CORS_ORIGINS` 包含前端地址（默认 `http://localhost:5173`），修改后需重启服务。

**Q：订单号重复？**
单号由「查当日最大号 + 1」生成，并发下可能撞号，后端已内置最多 5 次重试。

---

## 十一、一阶段未实现（后续阶段）

- 库存扣减 / 库存流水写入（`inventory_history` 一阶段只建表）
- 库存预留（`reserved_quantity` 字段已建，暂未使用）
- 采购单与采购入库、审批流程
- 出库单、单据打印、消息通知、Excel 导入导出
