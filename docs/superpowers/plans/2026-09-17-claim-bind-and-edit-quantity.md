# 接单关联货号与运营修改数量 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 仓储在接单抽屉内完成货号关联，运营随后可修改最终出库数量并以该数量开始备货。

**Architecture:** 接单仍使用既有 `claim` 接口并在成功后刷新同一详情抽屉；`bind-sku` 继续在全部关联时自动转为状态 25。`confirm-quantity` 扩展为接收完整的行项目数量，在事务内先更新订单数量汇总，再预留库存和转为状态 30。

**Tech Stack:** Vue 3、Element Plus、FastAPI、Pydantic、SQLAlchemy、MySQL。

## Global Constraints

- 数量必须大于 0，最多保留两位小数，且请求必须覆盖订单所有明细一次。
- 只有状态 25 且订单创建人或管理员可以确认数量。
- 预留失败时不能持久化数量、汇总或状态变更。

---

### Task 1: 更新确认数量后端契约与事务

**Files:**
- Modify: `backend/app/schemas/order.py`
- Modify: `backend/app/api/order.py`
- Modify: `backend/tests/smoke_test.py`

- [ ] 写出请求完整性、数量重算和库存不足回滚的失败测试。
- [ ] 增加 `ConfirmQuantityIn` / 明细 schema，并让接口锁定订单后验证全部 `item_id`、更新明细 `count`/`total_price` 和订单汇总。
- [ ] 在更新后的数量上执行可用量检查与预留，提交后返回详情。
- [ ] 运行 `python tests/smoke_test.py`。

### Task 2: 运营数量编辑界面与请求

**Files:**
- Modify: `frontend/src/api/order.js`
- Modify: `frontend/src/views/operator/components/OrderDetailDrawer.vue`
- Modify: `frontend/src/views/operator/OrderList.vue`
- Test: `frontend/tests/operator-edit-quantity-contract.test.mjs`

- [ ] 写出状态 25 显示输入框且提交 `{ items }` 的失败契约测试。
- [ ] 将确认弹窗替换为订单详情内每行的数字输入，并提交当前编辑值。
- [ ] 更新列表操作以打开同一个可编辑详情抽屉。
- [ ] 运行该契约测试与 `npm run build`。

### Task 3: 仓储接单后同抽屉关联体验

**Files:**
- Modify: `frontend/src/views/warehouse/PendingOrders.vue`
- Modify: `frontend/src/views/warehouse/components/WarehouseOrderDetailDrawer.vue`
- Modify: `frontend/tests/warehouse-order-detail-drawer-claim.test.mjs`

- [ ] 写出接单成功后抽屉持续展示货号关联区的失败契约测试。
- [ ] 统一列表直接接单与详情接单的成功后动作：刷新列表、保持/打开详情抽屉、刷新订单详情。
- [ ] 运行两份前端契约测试与 `npm run build`。
