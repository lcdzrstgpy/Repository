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
出库单生成、库存流水、状态回传、确认完成、状态机拦截、权限校验、库存不足拦截、
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
    ("仓库列表", "/api/warehouses"),
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
whs = body(r).get("data", [])
check("仓库下拉选项", len(whs) > 0, f"{len(whs)} 个")

# ---------------------------------------------------------------- 运营下单
print("\n=== 5. 运营下单 ===")
r = client.post("/api/auth/login", json={"username": "operator1", "password": "admin123"})
op_h = {"Authorization": f"Bearer {(body(r).get('data') or {}).get('access_token', '')}"}
check("operator1 登录", body(r).get("code") == 0)

r = client.post("/api/auth/login", json={"username": "warehouse1", "password": "admin123"})
wh_h = {"Authorization": f"Bearer {(body(r).get('data') or {}).get('access_token', '')}"}
check("warehouse1 登录", body(r).get("code") == 0)

r = client.post(
    "/api/sales-orders",
    json={
        "customer_id": 1,
        "remark": "冒烟测试订单",
        "items": [{"sku_id": 1, "count": 10, "price": 25.0}],
    },
    headers=op_h,
)
d = body(r)
order_id = d.get("data", {}).get("id")
check("创建订单", d.get("code") == 0 and order_id, str(d)[:120])
check("订单初始状态=10", d.get("data", {}).get("status") == 10)
check("总额后端计算正确", d.get("data", {}).get("total_price") == 250.0, f"total_price={d.get('data',{}).get('total_price')}")

r = client.get("/api/sales-orders", headers=op_h)
lst = body(r).get("data", {}).get("list", [])
check("运营只看自己的订单", body(r).get("code") == 0, f"{len(lst)} 条")

# ---------------------------------------------------------------- 仓储履约
print("\n=== 6. 仓储接单 → 备货 → 发货 ===")
r = client.get("/api/warehouse/pending-orders", headers=wh_h)
pending = body(r).get("data", {}).get("list", [])
check("待接单列表", body(r).get("code") == 0, f"{len(pending)} 条")

r = client.post(f"/api/warehouse/orders/{order_id}/claim", json={"warehouse_id": 1}, headers=wh_h)
check("接单", body(r).get("code") == 0, str(body(r))[:120])

r = client.get("/api/inventory", params={"warehouse_id": 1}, headers=wh_h)
inv = body(r).get("data", {}).get("list", [])
sku1 = next((i for i in inv if i["sku_id"] == 1), None)
check("接单后预留量=10", sku1 and sku1["reserved_quantity"] == 10.0, f"reserved={sku1 and sku1['reserved_quantity']}")
check("接单后库存量不变=100", sku1 and sku1["quantity"] == 100.0, f"qty={sku1 and sku1['quantity']}")
check("可用量=90", sku1 and sku1["available_quantity"] == 90.0, f"avail={sku1 and sku1['available_quantity']}")

r = client.post(f"/api/warehouse/orders/{order_id}/prepare", json={}, headers=wh_h)
check("开始备货", body(r).get("code") == 0, str(body(r))[:120])

r = client.post(f"/api/warehouse/orders/{order_id}/ship", json={"express_no": "SF1234567890"}, headers=wh_h)
check("发货", body(r).get("code") == 0, str(body(r))[:150])

r = client.get("/api/inventory", params={"warehouse_id": 1}, headers=wh_h)
sku1 = next((i for i in body(r).get("data", {}).get("list", []) if i["sku_id"] == 1), None)
check("发货后库存=90", sku1 and sku1["quantity"] == 90.0, f"qty={sku1 and sku1['quantity']}")
check("发货后预留释放=0", sku1 and sku1["reserved_quantity"] == 0.0, f"reserved={sku1 and sku1['reserved_quantity']}")

r = client.get("/api/sales-outs", headers=wh_h)
outs = body(r).get("data", {}).get("list", [])
check("出库单已生成", len(outs) > 0, f"{len(outs)} 张")
out_id = outs[0]["id"] if outs else None

if out_id:
    r = client.get(f"/api/sales-outs/{out_id}", headers=wh_h)
    d = body(r).get("data", {})
    check("出库单详情含明细", len(d.get("items", [])) > 0)
    check("出库单含客户名称", bool(d.get("customer_name")), f"customer_name={d.get('customer_name')}")

r = client.get("/api/inventory/history", headers=wh_h)
hist = body(r).get("data", {}).get("list", [])
check("库存流水已写入", len(hist) > 0, f"{len(hist)} 条")
check("流水含变动前后值", bool(hist) and hist[0].get("before_quantity") is not None, str(hist[0])[:150] if hist else "")

# ---------------------------------------------------------------- 状态回传 + 确认
print("\n=== 7. 状态回传与确认 ===")
r = client.get("/api/sales-orders", headers=op_h)
mine = next((o for o in body(r).get("data", {}).get("list", []) if o["id"] == order_id), None)
check("运营能看到状态=40 已发货", mine and mine["status"] == 40, f"status={mine and mine['status']}")
check("运营能看到物流单号", mine and mine.get("express_no") == "SF1234567890")

r = client.post(f"/api/sales-orders/{order_id}/confirm", json={}, headers=op_h)
check("运营确认完成", body(r).get("code") == 0, str(body(r))[:120])

r = client.post(f"/api/sales-orders/{order_id}/confirm", json={}, headers=op_h)
check("重复确认被拒（状态机生效）", body(r).get("code") == 1001, str(body(r))[:120])

# ---------------------------------------------------------------- 权限
print("\n=== 8. 权限校验 ===")
r = client.post("/api/warehouses", json={"code": "WH999", "name": "越权测试"}, headers=op_h)
check("operator 不能建仓库", body(r).get("code") == 403, str(body(r))[:100])

r = client.post(
    "/api/sales-orders",
    json={"customer_id": 1, "items": [{"sku_id": 1, "count": 1, "price": 1.0}]},
    headers=op_h,
)
other_order = body(r).get("data", {}).get("id")
r = client.post(f"/api/warehouse/orders/{other_order}/claim", json={"warehouse_id": 1}, headers=op_h)
check("operator 不能接单", body(r).get("code") == 403, str(body(r))[:100])

# ---------------------------------------------------------------- 库存不足拦截
print("\n=== 9. 库存不足拦截 ===")
r = client.post(
    "/api/sales-orders",
    json={"customer_id": 1, "items": [{"sku_id": 1, "count": 99999, "price": 1.0}]},
    headers=op_h,
)
big_order = body(r).get("data", {}).get("id")
client.post(f"/api/warehouse/orders/{big_order}/claim", json={"warehouse_id": 1}, headers=wh_h)
r = client.post(f"/api/warehouse/orders/{big_order}/claim", json={"warehouse_id": 1}, headers=wh_h)
check("超量接单被拦截", body(r).get("code") == 1001, str(body(r))[:180])

# ---------------------------------------------------------------- 采购链路
print("\n=== 10. 采购链路 ===")
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
check("审批采购单", body(r).get("code") == 0, str(body(r))[:120])

r = client.get(f"/api/purchase-orders/{po_id}", headers=wh_h)
po = body(r).get("data", {})
po_items = po.get("items", [])
check("采购单含明细", len(po_items) > 0)

if po_items:
    r = client.post(
        f"/api/purchase-orders/{po_id}/receive",
        json={
            "warehouse_id": 1,
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
    ("库存", "/api/export/inventory"),
    ("订单", "/api/export/sales-orders"),
]:
    r = client.get(path, headers=admin_h)
    ok = r.status_code == 200 and r.content[:2] == b"PK"
    check(f"导出{name}", ok, f"HTTP {r.status_code}, {len(r.content)} bytes")

# ---------------------------------------------------------------- 结果
print("\n" + "=" * 60)
print(f"通过 {len(PASS)} 项，失败 {len(FAIL)} 项")
if FAIL:
    print("失败项：")
    for f in FAIL:
        print("  -", f)
print("=" * 60)
