"""离线端到端冒烟测试：用 SQLite 顶替 MySQL，跑通完整业务链路。

用法（在 backend/ 目录下执行）：

    python tests/smoke_test.py

不需要 MySQL，也不需要启动后端服务——脚本自己建库、灌初始化数据，
再用 FastAPI 的 TestClient 直接打接口。每次运行都会重建一个干净的
smoke_test.db（已在 .gitignore 中忽略）。

实现上用了两个补丁让项目能在 SQLite 上跑：

  1. DATABASE_URL 指向 SQLite 文件
  2. 给 SQLite 方言注册 TINYINT / BigInteger 的编译规则
     - TINYINT：SQLite 方言不认识 mysql.TINYINT，否则建表报 UnsupportedCompilationError
     - BigInteger：SQLite 只有 INTEGER PRIMARY KEY 才是 rowid 别名（可自增），
       BIGINT 不行，否则插入报 NOT NULL constraint failed: xxx.id
     这两个都是 SQLite 特有问题，MySQL 下完全正常，不是项目代码的缺陷。

覆盖范围：认证、基础数据 CRUD 与筛选、运营下单、接单预留、备货、发货实扣、
出库单生成、库存流水、发货即完成、状态机拦截、权限校验、库存不足拦截、
采购全链路、Excel 导出。

注意：SQLite 不支持 SELECT ... FOR UPDATE（SQLAlchemy 会静默忽略），
所以本脚本无法验证并发场景下的行锁行为，那部分需要真实 MySQL 才能测。
"""

import os
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BACKEND_DIR / "smoke_test.db"
if DB_PATH.exists():
    DB_PATH.unlink()

# 必须在导入 app 之前设置环境变量
os.environ["DATABASE_URL"] = f"sqlite:///{DB_PATH}"
os.environ["DEBUG"] = "true"
os.environ["DB_ECHO"] = "false"

sys.path.insert(0, str(BACKEND_DIR))

from sqlalchemy import BigInteger
from sqlalchemy.dialects.mysql import TINYINT
from sqlalchemy.ext.compiler import compiles


@compiles(TINYINT, "sqlite")
def _tinyint_sqlite(type_, compiler, **kw):
    return "INTEGER"


@compiles(BigInteger, "sqlite")
def _bigint_sqlite(type_, compiler, **kw):
    # SQLite 只有 INTEGER PRIMARY KEY 才是 rowid 别名（可自增），BIGINT 不行。
    # MySQL 下 BIGINT AUTO_INCREMENT 是正常的，这里只是让 SQLite 能跑。
    return "INTEGER"


from fastapi.testclient import TestClient

from app.core.database import Base, engine
import app.models  # noqa: F401  确保全部模型注册
from app.main import app
import init_data

PASS, FAIL = [], []


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    mark = "OK  " if cond else "FAIL"
    print(f"  [{mark}] {name}" + (f"  -> {detail}" if detail else ""))
    return cond


def body(r):
    try:
        return r.json()
    except Exception:
        return {"_raw": r.text[:200]}


# ---------------------------------------------------------------- 建表 + 初始化
print("\n=== 1. 建表 ===")
Base.metadata.create_all(engine)
check("建表成功", True, f"{len(Base.metadata.tables)} 张表")

print("\n=== 2. 初始化数据 ===")
rc = init_data.main()
check("init_data.main() 返回 0", rc == 0, f"rc={rc}")

client = TestClient(app)

# ---------------------------------------------------------------- 认证
print("\n=== 3. 认证 ===")
r = client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
d = body(r)
check("admin 用 admin123 登录成功", d.get("code") == 0, str(d)[:120])
admin_h = {"Authorization": f"Bearer {(d.get('data') or {}).get('access_token', '')}"}

r = client.post("/api/auth/login", json={"username": "admin", "password": "wrong-password"})
check("错误密码被拒绝", body(r).get("code") != 0, str(body(r))[:80])

r = client.get("/api/auth/me", headers=admin_h)
check("GET /api/auth/me", body(r).get("code") == 0)

r = client.get("/api/sales-orders")
check("未带 token 被拒绝", body(r).get("code") == 401, str(body(r))[:80])

# ---------------------------------------------------------------- 基础数据
print("\n=== 4. 基础数据 ===")
for name, path in [
    ("商品列表", "/api/products"),
    ("SKU 列表", "/api/skus"),
    ("往来单位", "/api/partners"),
    ("用户列表", "/api/users"),
]:
    r = client.get(path, headers=admin_h)
    d = body(r)
    n = len(d.get("data", {}).get("list", [])) if d.get("code") == 0 else -1
    check(f"GET {path}", d.get("code") == 0, f"{n} 条")

r = client.get("/api/partners", params={"type": 2}, headers=admin_h)
d = body(r)
sup = d.get("data", {}).get("list", [])
check("partner 按 type=2 筛选", d.get("code") == 0 and all(p["type"] == 2 for p in sup), f"{len(sup)} 个供应商")

r = client.get("/api/users", params={"role": "warehouse"}, headers=admin_h)
d = body(r)
us = d.get("data", {}).get("list", [])
check("user 按 role 筛选", d.get("code") == 0 and all(u["role"] == "warehouse" for u in us), f"{len(us)} 个仓储")

r = client.get("/api/skus/options", headers=admin_h)
skus = body(r).get("data", [])
check("SKU 下拉选项", len(skus) > 0, f"{len(skus)} 个")
r = client.get("/api/warehouses/options", headers=admin_h)
check("仓库管理接口已下线", body(r).get("code") == 404, str(body(r))[:120])

# ---------------------------------------------------------------- 运营下单
print("\n=== 5. 运营下单 ===")
r = client.post("/api/auth/login", json={"username": "operator1", "password": "admin123"})
op_h = {"Authorization": f"Bearer {(body(r).get('data') or {}).get('access_token', '')}"}
check("operator1 登录", body(r).get("code") == 0)

r = client.post("/api/auth/login", json={"username": "warehouse1", "password": "admin123"})
wh_h = {"Authorization": f"Bearer {(body(r).get('data') or {}).get('access_token', '')}"}
check("warehouse1 登录", body(r).get("code") == 0)

r = client.get("/api/stock-transfers", headers=wh_h)
check("移库功能已移除", body(r).get("code") == 404, str(body(r))[:120])
r = client.get("/api/stock-takes", headers=wh_h)
check("盘点功能已移除", body(r).get("code") == 404, str(body(r))[:120])

# 运营货号库存查询：仅展示单仓库存余额，不提供库存写入能力。
r = client.get("/api/item-query", params={"keyword": "SKU001"}, headers=op_h)
item_rows = body(r).get("data", [])
sku001 = next((item for item in item_rows if item.get("item_no") == "SKU001"), None)
check(
    "运营可查询货号库存",
    body(r).get("code") == 0
    and sku001 is not None
    and {"quantity", "available_quantity"} <= set(sku001.keys()),
    str(body(r))[:180],
)
r = client.get("/api/inventory", headers=op_h)
check("运营不能访问仓储库存操作台接口", body(r).get("code") == 403, str(body(r))[:120])

r = client.post(
    "/api/sales-orders",
    json={
        "no": "TB20260917999",
        "remark": "冒烟测试订单",
        "items": [
            {"product_name": "商品A", "sku_code": "SKU001", "count": 10, "expect_price": 25.0},
            {"product_name": "全新商品X", "is_new": 1, "count": 5, "expect_price": 8.5},
        ],
    },
    headers=op_h,
)
d = body(r)
order_id = d.get("data", {}).get("id")
check("创建订单（一行填货号 + 一行勾新品）", d.get("code") == 0 and order_id, str(d)[:120])
check("订单初始状态=10", d.get("data", {}).get("status") == 10)
check("总额后端计算正确", d.get("data", {}).get("total_price") == 292.5, f"total_price={d.get('data',{}).get('total_price')}")
check("明细行数=2", d.get("data", {}).get("item_count") == 2)
check("未关联货号行数=2", d.get("data", {}).get("unbound_count") == 2)
check("all_sku_bound=false", d.get("data", {}).get("all_sku_bound") is False)

r = client.post(
    "/api/sales-orders",
    json={"no": "TB-BAD-001", "items": [{"product_name": "缺货号商品", "count": 1, "expect_price": 1.0}]},
    headers=op_h,
)
check("货号与新品都不填被拒", body(r).get("code") != 0, str(body(r))[:100])

r = client.post(
    "/api/sales-orders",
    json={
        "no": "TB-DECIMAL-001",
        "items": [{"product_name": "小数数量商品", "sku_code": "SKU001", "count": 1.5, "expect_price": 1.0}],
    },
    headers=op_h,
)
check("创建订单小数数量被拒", body(r).get("code") == 400, str(body(r))[:100])

r = client.post(
    "/api/sales-orders",
    json={
        "no": "TB20260917999",
        "items": [{"product_name": "重复单号", "sku_code": "SKU001", "count": 1, "expect_price": 1.0}],
    },
    headers=op_h,
)
check("订单号重复被拒", body(r).get("code") == 1001, str(body(r))[:100])

r = client.get("/api/sales-orders", headers=op_h)
lst = body(r).get("data", {}).get("list", [])
check("运营只看自己的订单", body(r).get("code") == 0, f"{len(lst)} 条")

# ---------------------------------------------------------------- 仓储履约
print("\n=== 6. 仓储接单 → 绑定货号 → 备货 → 发货 ===")
r = client.get("/api/warehouse/pending-orders", headers=wh_h)
pending = body(r).get("data", {}).get("list", [])
check("待接单列表", body(r).get("code") == 0, f"{len(pending)} 条")

r = client.post(f"/api/warehouse/orders/{order_id}/claim", json={"warehouse_id": 1}, headers=wh_h)
check("接单", body(r).get("code") == 0, str(body(r))[:120])

r = client.get("/api/inventory", params={"warehouse_id": 1}, headers=wh_h)
sku1 = next((i for i in body(r).get("data", {}).get("list", []) if i["sku_id"] == 1), None)
check("接单阶段不预留（货号还没绑）", sku1 and sku1["reserved_quantity"] == 0.0, f"reserved={sku1 and sku1['reserved_quantity']}")

r = client.post(f"/api/warehouse/orders/{order_id}/prepare", json={}, headers=wh_h)
check("prepare 已废弃（返回 1001）", body(r).get("code") == 1001, str(body(r))[:140])

r = client.get(f"/api/sales-orders/{order_id}", headers=wh_h)
items = body(r).get("data", {}).get("items", [])
it_old = next((i for i in items if i.get("sku_code")), None)
it_new = next((i for i in items if i.get("is_new") == 1), None)

bind_payload = {"items": []}
if it_old:
    bind_payload["items"].append({"item_id": it_old["id"], "sku_code": it_old["sku_code"]})
if it_new:
    bind_payload["items"].append(
        {
            "item_id": it_new["id"],
            "new_sku": {
                "sku_code": "NEW-SMOKE-001",
                "product_name": it_new["product_name"],
                "category_level1": "测试分类",
                "spec": "标准",
                "price": 8.5,
            },
        }
    )
r = client.post(f"/api/warehouse/orders/{order_id}/bind-sku", json=bind_payload, headers=wh_h)
check("绑定货号（关联已有 + 新建）", body(r).get("code") == 0, str(body(r))[:180])
check("绑定后 all_sku_bound=true", body(r).get("data", {}).get("all_sku_bound") is True)
check(
    "绑定后自动进入「数量待确认」(25)",
    body(r).get("data", {}).get("status") == 25,
    f"status={body(r).get('data', {}).get('status')}",
)
check(
    "状态文案=数量待确认",
    body(r).get("data", {}).get("status_text") == "数量待确认",
    str(body(r).get("data", {}).get("status_text")),
)

if it_old:
    r = client.post(
        f"/api/warehouse/orders/{order_id}/bind-sku",
        json={"items": [{"item_id": it_old["id"], "sku_code": it_old["sku_code"]}]},
        headers=wh_h,
    )
    check("已关联货号不可重复修改", body(r).get("code") == 1001, str(body(r))[:130])

# 新建的 SKU 初始库存为 0，先补货（模拟采购入库后的状态）
r = client.get(f"/api/sales-orders/{order_id}", headers=wh_h)
bound_items = body(r).get("data", {}).get("items", [])
new_item = next((i for i in bound_items if i.get("is_new") == 1 and i.get("sku_id")), None)
if new_item:
    r = client.post(
        "/api/inventory/adjust",
        json={"sku_id": new_item["sku_id"], "warehouse_id": 1, "quantity": 100, "remark": "冒烟测试补货"},
        headers=wh_h,
    )
    check("为新货号补货（模拟采购入库）", body(r).get("code") == 0, str(body(r))[:150])

r = client.post(
    f"/api/sales-orders/{order_id}/confirm-quantity",
    json={
        "items": [
            {"item_id": it_old["id"], "count": 8},
            {"item_id": it_new["id"], "count": 3},
        ]
    },
    headers=op_h,
)
check("运营修改数量并确认（25 → 30）", body(r).get("code") == 0, str(body(r))[:150])
check("确认后状态=30 备货中", body(r).get("data", {}).get("status") == 30)
check("确认后订单总数量按修改值重算", body(r).get("data", {}).get("total_count") == 11.0)
check("确认后订单总成本按修改值重算", body(r).get("data", {}).get("total_price") == 225.5)
confirmed_items = body(r).get("data", {}).get("items", [])
confirmed_counts = {item["id"]: item["count"] for item in confirmed_items}
check("确认后明细数量按修改值保存", confirmed_counts == {it_old["id"]: 8.0, it_new["id"]: 3.0}, str(confirmed_counts))

r = client.get("/api/inventory", params={"warehouse_id": 1}, headers=wh_h)
sku1 = next((i for i in body(r).get("data", {}).get("list", []) if i["sku_id"] == 1), None)
check("确认数量不预留库存", sku1 and sku1["reserved_quantity"] == 0.0, f"reserved={sku1 and sku1['reserved_quantity']}")
check("备货后库存量不变=100", sku1 and sku1["quantity"] == 100.0, f"qty={sku1 and sku1['quantity']}")
check("确认数量后可用量仍为100", sku1 and sku1["available_quantity"] == 100.0, f"avail={sku1 and sku1['available_quantity']}")

r = client.post(f"/api/warehouse/orders/{order_id}/ship", json={"express_no": "SF1234567890"}, headers=wh_h)
check("发货", body(r).get("code") == 0, str(body(r))[:150])

r = client.get("/api/inventory", params={"warehouse_id": 1}, headers=wh_h)
sku1 = next((i for i in body(r).get("data", {}).get("list", []) if i["sku_id"] == 1), None)
check("发货后库存=92", sku1 and sku1["quantity"] == 92.0, f"qty={sku1 and sku1['quantity']}")
check("发货后预留仍为0", sku1 and sku1["reserved_quantity"] == 0.0, f"reserved={sku1 and sku1['reserved_quantity']}")

r = client.get("/api/sales-outs", headers=wh_h)
outs = body(r).get("data", {}).get("list", [])
check("出库单已生成", len(outs) > 0, f"{len(outs)} 张")
out_id = outs[0]["id"] if outs else None

if out_id:
    r = client.get(f"/api/sales-outs/{out_id}", headers=wh_h)
    d = body(r).get("data", {})
    check("出库单详情含明细", len(d.get("items", [])) > 0)
    check(
        "出库单明细含商品名",
        any(i.get("product_name") for i in d.get("items", [])),
        str(d.get("items", [])[:1])[:120],
    )

r = client.get("/api/inventory/history", headers=wh_h)
hist = body(r).get("data", {}).get("list", [])
check("库存流水已写入", len(hist) > 0, f"{len(hist)} 条")
check("流水含变动前后值", bool(hist) and hist[0].get("before_quantity") is not None, str(hist[0])[:150] if hist else "")

# ---------------------------------------------------------------- 发货即完成
print("\n=== 7. 发货即完成（运营无需二次确认） ===")
r = client.get("/api/sales-orders", headers=op_h)
mine = next((o for o in body(r).get("data", {}).get("list", []) if o["id"] == order_id), None)
check("运营看到状态=50 已完成", mine and mine["status"] == 50, f"status={mine and mine['status']}")
check("状态文案为已完成", mine and mine.get("status_text") == "已完成", str(mine)[:150])
check("运营能看到物流单号", mine and mine.get("express_no") == "SF1234567890")

r = client.post(f"/api/sales-orders/{order_id}/confirm", json={}, headers=op_h)
check("确认完成接口已下线", body(r).get("code") == 404, str(body(r))[:120])

r = client.post(f"/api/warehouse/orders/{order_id}/ship", json={"express_no": "SF-AGAIN"}, headers=wh_h)
check("重复发货被拒（状态机生效）", body(r).get("code") == 1001, str(body(r))[:120])

# ---------------------------------------------------------------- 权限
print("\n=== 8. 权限校验 ===")
r = client.post("/api/warehouses", json={"code": "WH999", "name": "越权测试"}, headers=op_h)
check("仓库创建接口已下线", body(r).get("code") == 404, str(body(r))[:100])

# 管理员只负责全局查看与主数据/人员维护，不能代替运营直接下单。
r = client.post(
    "/api/sales-orders",
    json={
        "no": "TB-ADMIN-BLOCK-001",
        "items": [{"product_name": "管理员越权下单", "sku_code": "SKU001", "count": 1, "expect_price": 1.0}],
    },
    headers=admin_h,
)
check("管理员不能代运营创建订单", body(r).get("code") == 403, str(body(r))[:100])

r = client.get("/api/sales-orders", headers=admin_h)
check("管理员可全局查看订单", body(r).get("code") == 0, str(body(r))[:100])

r = client.get("/api/purchase-orders", headers=admin_h)
check("管理员可查看采购单", body(r).get("code") == 0, str(body(r))[:100])

r = client.post(
    "/api/sales-orders",
    json={
        "no": "TB-PERM-001",
        "items": [{"product_name": "越权测试品", "sku_code": "SKU001", "count": 1, "expect_price": 1.0}],
    },
    headers=op_h,
)
other_order = (body(r).get("data") or {}).get("id")
r = client.post(
    f"/api/sales-orders/{other_order}/cancel",
    json={"cancel_reason": "管理员越权测试"},
    headers=admin_h,
)
check("管理员不能取消订单", body(r).get("code") == 403, str(body(r))[:100])

r = client.post(f"/api/warehouse/orders/{other_order}/claim", json={"warehouse_id": 1}, headers=op_h)
check("operator 不能接单", body(r).get("code") == 403, str(body(r))[:100])

# ---------------------------------------------------------------- 库存不足拦截
print("\n=== 9. 库存不足拦截 ===")
r = client.post(
    "/api/sales-orders",
    json={
        "no": "TB-OVER-001",
        "items": [{"product_name": "超量商品", "sku_code": "SKU001", "count": 99999, "expect_price": 1.0}],
    },
    headers=op_h,
)
big_order = (body(r).get("data") or {}).get("id")
client.post(f"/api/warehouse/orders/{big_order}/claim", json={"warehouse_id": 1}, headers=wh_h)

r = client.get(f"/api/sales-orders/{big_order}", headers=wh_h)
big_items = body(r).get("data", {}).get("items", [])
if big_items:
    client.post(
        f"/api/warehouse/orders/{big_order}/bind-sku",
        json={"items": [{"item_id": big_items[0]["id"], "sku_code": "SKU001"}]},
        headers=wh_h,
    )
big_item_id = big_items[0]["id"] if big_items else None
r = client.post(
    f"/api/sales-orders/{big_order}/confirm-quantity",
    json={"items": [{"item_id": big_item_id, "count": 1.5}]},
    headers=op_h,
)
check("确认数量小数被拒", body(r).get("code") == 400, str(body(r))[:180])
r = client.post(
    f"/api/sales-orders/{big_order}/confirm-quantity",
    json={"items": [{"item_id": big_item_id, "count": 99999}]},
    headers=op_h,
)
check("库存不足仍可确认数量并进入备货", body(r).get("code") == 0 and body(r).get("data", {}).get("status") == 30, str(body(r))[:180])
r = client.post(f"/api/warehouse/orders/{big_order}/ship", json={"express_no": "SF-OVER-001"}, headers=wh_h)
check("仓储发货时拦截库存不足", body(r).get("code") == 1001, str(body(r))[:180])

# ---------------------------------------------------------------- 采购链路
print("\n=== 10. 采购链路 ===")
# 缺货订单候选：仅返回备货中且按当前可用库存确有短缺的订单，并给出自动采购数量。
r = client.get("/api/purchase-orders/candidates", headers=wh_h)
candidates = body(r).get("data", [])
candidate = next((row for row in candidates if row.get("id") == big_order), None)
check("缺货订单可作为采购候选", body(r).get("code") == 0 and candidate, str(body(r))[:180])
candidate_item = (candidate or {}).get("items", [None])[0]
check(
    "采购候选按订单需求减可用库存生成短缺数量",
    candidate_item and candidate_item.get("suggested_purchase", 0) > 0,
    str(candidate_item)[:180],
)

# 仓管创建后即可在采购单管理页完成采购并入库，不再依赖审批角色。
r = client.post(
    "/api/purchase-orders",
    json={
        "supplier_id": sup[0]["id"] if sup else 3,
        "sales_order_id": big_order,
        "express_no": "SF-SMOKE-001",
        "remark": "缺货订单自动补货",
        "items": [
            {
                "sku_id": candidate_item["sku_id"],
                "count": candidate_item["suggested_purchase"],
                "price": 0,
            }
        ]
        if candidate_item
        else [{"sku_id": 1, "count": 1, "price": 0}],
    },
    headers=wh_h,
)
candidate_po = body(r).get("data", {})
candidate_po_id = candidate_po.get("id")
check("从缺货订单创建采购单", body(r).get("code") == 0 and candidate_po_id, str(body(r))[:180])

if candidate_po_id:
    candidate_po_items = candidate_po.get("items", [])
    r = client.post(
        f"/api/purchase-orders/{candidate_po_id}/receive",
        json={
            "items": [
                {"order_item_id": item["id"], "count": item["count"]}
                for item in candidate_po_items
            ],
        },
        headers=wh_h,
    )
    check("仓管可直接采购完成并入库", body(r).get("code") == 0, str(body(r))[:180])

# 采购价上限校验（契约 17.3）：SKU001 在 TB20260917999 里的预计成本是 25.00
r = client.post(
    "/api/purchase-orders",
    json={
        "supplier_id": sup[0]["id"] if sup else 3,
        "sales_order_id": order_id,
        "items": [{"sku_id": 1, "count": 1, "price": 999.0}],
    },
    headers=wh_h,
)
check("采购价高于预计成本被拒", body(r).get("code") == 1001, str(body(r))[:150])

r = client.post(
    "/api/purchase-orders",
    json={
        "supplier_id": sup[0]["id"] if sup else 3,
        "expect_date": "2026-09-20",
        "remark": "冒烟测试采购",
        "items": [{"sku_id": 2, "count": 50, "price": 12.0}],
    },
    headers=wh_h,
)
d = body(r)
po_id = d.get("data", {}).get("id")
check("创建采购单", d.get("code") == 0 and po_id, str(d)[:150])
check("采购单初始状态=10", d.get("data", {}).get("status") == 10)

r = client.post(f"/api/purchase-orders/{po_id}/approve", json={}, headers=admin_h)
check("管理员不能审批采购单", body(r).get("code") == 403, str(body(r))[:120])

r = client.get(f"/api/purchase-orders/{po_id}", headers=wh_h)
po = body(r).get("data", {})
po_items = po.get("items", [])
check("采购单含明细", len(po_items) > 0)

if po_items:
    r = client.post(
        f"/api/purchase-orders/{po_id}/receive",
        json={
            "remark": "全部到货",
            "items": [{"order_item_id": po_items[0]["id"], "count": 50}],
        },
        headers=wh_h,
    )
    check("收货入库", body(r).get("code") == 0, str(body(r))[:150])

r = client.get("/api/inventory", params={"warehouse_id": 1}, headers=wh_h)
sku2 = next((i for i in body(r).get("data", {}).get("list", []) if i["sku_id"] == 2), None)
check("采购入库后库存增加", sku2 and sku2["quantity"] > 100.0, f"qty={sku2 and sku2['quantity']}")

r = client.get("/api/purchase-orders", headers=wh_h)
pos = body(r).get("data", {}).get("list", [])
check("采购单列表", body(r).get("code") == 0, f"{len(pos)} 条")

# ---------------------------------------------------------------- 导出
print("\n=== 11. Excel 导出 ===")
for name, path in [
    ("商品", "/api/export/products"),
    ("SKU", "/api/export/skus"),
    ("订单", "/api/export/sales-orders"),
]:
    r = client.get(path, headers=admin_h)
    ok = r.status_code == 200 and r.content[:2] == b"PK"
    check(f"导出{name}", ok, f"HTTP {r.status_code}, {len(r.content)} bytes")

r = client.get("/api/export/inventory", headers=wh_h)
check("仓储可导出库存", r.status_code == 200 and r.content[:2] == b"PK", f"HTTP {r.status_code}, {len(r.content)} bytes")

# ---------------------------------------------------------------- 结果
print("\n" + "=" * 60)
print(f"通过 {len(PASS)} 项，失败 {len(FAIL)} 项")
if FAIL:
    print("失败项：")
    for f in FAIL:
        print("  -", f)
print("=" * 60)
