# 仓储管理系统 · 前端

公司内部仓储管理系统前端，对接 FastAPI 后端（`http://localhost:8000`）。
接口约定以 `docs/接口契约.md` 为唯一权威，字段名、状态值、路径均严格遵守。

## 技术栈

| 依赖 | 版本 | 说明 |
|---|---|---|
| Vue | ^3.5.13 | 组合式 API + `<script setup>` |
| Vite | ^5.4.11 | 构建工具 |
| Element Plus | ^2.8.8 | UI 组件库（中文语言包） |
| Pinia | ^2.2.6 | 状态管理（用户会话） |
| Vue Router | ^4.4.5 | 路由 + 角色守卫 |
| Axios | ^1.7.7 | HTTP 请求 |
| @element-plus/icons-vue | ^2.3.1 | 图标 |

## 环境要求

- Node.js ≥ 18（开发验证使用 Node 22.22.2）
- 后端服务已启动在 `http://localhost:8000`

## 安装与启动

```bash
cd frontend
npm install
npm run dev
```

浏览器打开 `http://localhost:5173`。

构建生产包：

```bash
npm run build     # 产物在 dist/
npm run preview   # 本地预览构建产物
```

## 目录结构

```
frontend/
├── index.html
├── vite.config.js          # /api 代理到 http://localhost:8000
├── package.json
└── src/
    ├── main.js             # 入口：Pinia / Router / Element Plus（中文）
    ├── App.vue
    ├── styles/index.css    # 全局基础样式
    ├── api/
    │   ├── request.js      # Axios 封装（token 注入 + 统一响应处理）
    │   ├── auth.js         # 登录 / 当前用户 / 退出
    │   ├── basic.js        # 仓库、商品、SKU、往来单位、用户 CRUD + 下拉选项
    │   ├── order.js        # 运营侧订单（创建 / 列表 / 详情 / 取消）
    │   ├── warehouse.js    # 仓储侧（待接单 / 接单 / 备货 / 发货）
    │   └── inventory.js    # 库存列表 / 库存流水
    ├── router/
    │   ├── index.js        # 创建路由 + 全局守卫（登录态 + 角色校验）
    │   └── routes.js       # 路由表（meta.roles 驱动菜单与权限）
    ├── stores/user.js      # 用户会话（token / 用户信息，持久化到 localStorage）
    ├── layout/index.vue    # 主布局（侧边栏按角色过滤 + 顶栏用户信息）
    ├── utils/
    │   ├── constants.js    # 状态枚举映射（订单状态、角色、类型等）
    │   ├── format.js       # 金额 / 数量格式化
    │   └── useCrud.js      # 基础数据 CRUD 通用逻辑
    └── views/
        ├── Login.vue
        ├── Dashboard.vue
        ├── operator/
        │   ├── OrderList.vue
        │   ├── OrderCreate.vue
        │   └── components/OrderDetailDrawer.vue
        ├── warehouse/
        │   ├── PendingOrders.vue
        │   ├── PreparingOrders.vue
        │   ├── MyOrders.vue
        │   └── InventoryList.vue
        └── basic/
            ├── WarehouseManage.vue
            ├── ProductManage.vue
            ├── SkuManage.vue
            ├── PartnerManage.vue
            └── UserManage.vue
```

## 页面与角色

| 菜单 | 路径 | 可访问角色 |
|---|---|---|
| 首页 | `/dashboard` | 全部角色 |
| 我的订单 | `/operator/orders` | operator、admin |
| 新建订单 | `/operator/orders/create` | operator、admin |
| 待接单 | `/warehouse/pending` | warehouse、admin |
| 备货中 | `/warehouse/preparing` | warehouse、admin |
| 我处理的单 | `/warehouse/mine` | warehouse、admin |
| 库存查询 | `/warehouse/inventory` | warehouse、admin |
| 仓库 / 商品 / SKU / 往来单位 / 用户管理 | `/basic/*` | 仅 admin |

## 关键实现说明

### 统一响应处理

`src/api/request.js` 中的响应拦截器：

- `code === 0`：直接返回 `data` 字段，业务代码无需再写 `.data.data`
- `code === 401`（或 HTTP 401）：清除 localStorage 中的 token 与用户信息，跳转 `/login`
- 其他 `code`：`ElMessage.error` 弹出后端返回的 `msg`，并 reject

请求拦截器自动附加请求头 `Authorization: Bearer <token>`。

### 状态映射

订单状态统一维护在 `src/utils/constants.js` 的 `ORDER_STATUS`：

| 值 | 文案 | el-tag 类型 |
|---|---|---|
| 10 | 待接单 | info（灰） |
| 20 | 已接单 | primary（蓝） |
| 30 | 备货中 | warning（橙） |
| 50 | 已完成 | success（绿） |
| 90 | 已取消 | danger（红） |

列表状态列优先使用后端返回的 `status_text`，缺失时回退到本地映射。

### 角色菜单与守卫

- 菜单由 `src/router/index.js` 的路由表 `meta.roles` 驱动，`layout/index.vue` 按当前角色过滤后渲染，未授权菜单不显示
- 全局前置守卫：未登录访问受保护页面跳 `/login`（带 `redirect`）；已登录访问 `/login` 跳 `/dashboard`；角色不匹配提示「无权限访问该页面」并回首页

### 分页

统一使用 `el-pagination`，参数名与契约一致：`page` / `page_size`，响应结构 `{ list, total, page, page_size }`。

### 状态流转按钮

| 操作 | 可用条件 | 位置 |
|---|---|---|
| 取消订单 | status ∈ {10, 20, 25, 30}，需填取消原因 | 我的订单 |
| 接单 | status = 10，需选仓库 | 待接单 |
| 开始备货 | status = 20 | 我处理的单（已接单页签） |
| 发货 | status = 30，需填物流单号 | 备货中 |

不可用状态下按钮置灰（`disabled`），与契约第六节流转表一致。

## 后端联调

- 前端开发端口 `5173`，通过 Vite `server.proxy` 将 `/api` 转发到 `http://localhost:8000`，因此**不需要后端单独配 CORS 也能本地联调**（后端仍建议开启 CORS）
- 后端需按契约第七节写入初始化数据，可用以下账号登录（密码均为 `admin123`）：

| 用户名 | 姓名 | 角色 |
|---|---|---|
| admin | 管理员 | admin |
| operator1 | 运营小王 | operator |
| warehouse1 | 仓管老李 | warehouse |

## 已知假设

1. **库存流水字段**：契约只给出 `GET /api/inventory/history` 的查询参数，未定义响应字段。前端按 `inventory_history` 表结构渲染（`quantity` / `before_quantity` / `after_quantity` / `order_no` / `order_type` / `created_at`），操作人优先取 `created_by_name`，缺失时回退 `created_by`。
2. **用户新增/修改**：契约未定义请求体，前端提交 `username` / `password` / `real_name` / `role` / `status`；编辑时密码留空则不提交 `password` 字段。
3. **首页统计**：契约无统计接口，前端用 `GET /api/sales-orders` 的 `total` 分别统计待接单（10）、备货中（30）、已完成（50）与全部订单数（每次 `page_size=1`）。
4. **我处理的单**：契约的 `status` 查询参数为单值，页面用三个页签（已接单 20 / 数量待确认 25 / 已完成 50）分别查询。
5. **approver 角色**：契约注明一阶段仅建数据、不实现界面，前端未做审批页面，仅保证该角色登录后能进入首页。
6. 生产构建产物为静态文件，部署时需由 Nginx 等将 `/api` 反向代理到后端，或改为直接使用后端地址。
