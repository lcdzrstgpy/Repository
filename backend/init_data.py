"""初始化数据脚本（幂等，可重复执行）。

用法：
    cd backend
    python3 init_data.py

按《接口契约》第七节写入：
    3 个用户 / 2 个仓库 / 3 个商品各 1 个 SKU / 2 客户 + 2 供应商 /
    主仓 3 个 SKU 各 100 库存 / 1 条 status=10 的示例待接单订单（含 2 条明细）

幂等与覆盖语义：
    - 用户采用 upsert：已存在时覆盖 password_hash / real_name / role / status，
      因此本脚本既可用于首次初始化，也可用于把密码重置回默认值 admin123。
    - SKU 采用 upsert：已存在的 SKU 会覆盖 min_stock / spec / price / status，
      重复执行可把安全库存修回预期值（SKU001=50、SKU002=50、SKU003=20）。
    - 示例订单以单号 SAMPLE_ORDER_NO 作为幂等键，与 sql/init_data.sql 保持一致。

六阶段（契约 17.1 / 17.2 / 21.2）：订单改为「运营录入外部平台订单」模式，
示例订单不再关联客户，明细为「老品填货号 + 新品勾标记」两行，`sku_id` 均留空，
供仓储端「关联货号」流程测试（行 1 的货号 SKU001 在 product_sku 里真实存在）。
"""

import sys
from datetime import datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import Base, SessionLocal, engine
from app.core.security import hash_password
from app.models import (
    Inventory,
    Partner,
    Product,
    ProductSku,
    SalesOrder,
    SalesOrderItem,
    SysUser,
    Warehouse,
)

# 统一初始密码
DEFAULT_PASSWORD = "admin123"

# 示例订单的单号（运营录入的外部平台订单号），
# 同时作为两条初始化路径（本脚本 / sql/init_data.sql）统一的幂等键。
# 单号本身唯一，比用 remark 判断更可靠。
SAMPLE_ORDER_NO = "TB20260917001"

# 示例订单的备注文案，需与 sql/init_data.sql 中的 remark 保持一致
SAMPLE_ORDER_REMARK = "示例订单，供仓储端接单测试"


# ---------------------------------------------------------------- 各段初始化


def init_users(db: Session) -> dict[str, SysUser]:
    """3 个用户，密码统一 admin123（bcrypt 存储）。

    upsert 语义：用户已存在时不跳过，而是覆盖 password_hash / real_name / role / status，
    保证脚本可重复执行，并能把历史遗留的错误密码重置回 admin123。
    """
    rows = [
        ("admin", "管理员", "admin"),
        ("operator1", "运营小王", "operator"),
        ("warehouse1", "仓管老李", "warehouse"),
    ]
    password_hash = hash_password(DEFAULT_PASSWORD)
    users: dict[str, SysUser] = {}
    created = 0
    reset = 0
    for username, real_name, role in rows:
        user = db.scalar(select(SysUser).where(SysUser.username == username))
        if user is None:
            user = SysUser(
                username=username,
                password_hash=password_hash,
                real_name=real_name,
                role=role,
                status=1,
            )
            db.add(user)
            db.flush()
            created += 1
            print(f"[用户] 新建用户 {username}（密码 {DEFAULT_PASSWORD}）")
        else:
            # 已存在：覆盖密码与角色信息，确保脚本能把系统修回正确状态
            user.password_hash = password_hash
            user.real_name = real_name
            user.role = role
            user.status = 1
            reset += 1
            print(f"[用户] 用户 {username} 已存在，密码已重置为 {DEFAULT_PASSWORD}")
        users[username] = user
    print(
        f"[用户] 新增 {created} 个 / 重置 {reset} 个，当前共 {len(users)} 个"
        f"（密码统一 {DEFAULT_PASSWORD}）"
    )
    return users


def init_warehouses(db: Session) -> dict[str, Warehouse]:
    """2 个仓库：WH001 主仓、WH002 备用仓。"""
    rows = [
        ("WH001", "主仓", "上海市浦东新区张江路 1 号"),
        ("WH002", "备用仓", "上海市嘉定区曹安公路 100 号"),
    ]
    warehouses: dict[str, Warehouse] = {}
    created = 0
    for code, name, address in rows:
        warehouse = db.scalar(select(Warehouse).where(Warehouse.code == code))
        if warehouse is None:
            warehouse = Warehouse(code=code, name=name, address=address, status=1)
            db.add(warehouse)
            db.flush()
            created += 1
        warehouses[code] = warehouse
    print(f"[仓库] 新增 {created} 个，当前共 {len(warehouses)} 个")
    return warehouses


def init_products(db: Session) -> dict[str, ProductSku]:
    """3 个商品，各 1 个 SKU，编码 SKU001 ~ SKU003。

    SKU 采用 upsert：已存在时覆盖 min_stock / spec / price / status，
    保证脚本重复执行能把安全库存修回预期值。
    """
    rows = [
        # (商品编码, 商品名, 分类, 单位, SKU编码, 规格, 售价, 安全库存下限)
        ("P001", "商品A", "日用品", "个", "SKU001", "红色/大号", "25.00", "50.00"),
        ("P002", "商品B", "日用品", "个", "SKU002", "蓝色/中号", "18.50", "50.00"),
        ("P003", "商品C", "办公用品", "箱", "SKU003", "标准装", "99.00", "20.00"),
    ]
    skus: dict[str, ProductSku] = {}
    created_product = 0
    created_sku = 0
    updated_sku = 0
    for code, name, category, unit, sku_code, spec, price, min_stock in rows:
        product = db.scalar(select(Product).where(Product.code == code))
        if product is None:
            product = Product(code=code, name=name, category=category, unit=unit, status=1)
            db.add(product)
            db.flush()
            created_product += 1

        sku = db.scalar(select(ProductSku).where(ProductSku.sku_code == sku_code))
        if sku is None:
            sku = ProductSku(
                product_id=product.id,
                sku_code=sku_code,
                spec=spec,
                price=Decimal(price),
                min_stock=Decimal(min_stock),
                status=1,
            )
            db.add(sku)
            db.flush()
            created_sku += 1
        else:
            # 已存在：覆盖安全库存与基础字段，保证重复执行能把值修回预期
            sku.product_id = product.id
            sku.spec = spec
            sku.price = Decimal(price)
            sku.min_stock = Decimal(min_stock)
            sku.status = 1
            updated_sku += 1
        skus[sku_code] = sku
    print(
        f"[商品] 新增 {created_product} 个商品 / {created_sku} 个 SKU，"
        f"覆盖 {updated_sku} 个 SKU，当前共 {len(skus)} 个 SKU"
    )
    return skus


def init_partners(db: Session) -> dict[str, Partner]:
    """2 个客户（type=1）、2 个供应商（type=2）。"""
    rows = [
        ("某某贸易", 1, "张经理", "13800000001", "上海市黄浦区南京东路 100 号"),
        ("华东商贸", 1, "王经理", "13800000002", "杭州市西湖区文三路 200 号"),
        ("某某供应商", 2, "李厂长", "13900000001", "苏州市工业园区星湖街 300 号"),
        ("南方供应链", 2, "赵主管", "13900000002", "广州市白云区机场路 400 号"),
    ]
    partners: dict[str, Partner] = {}
    created = 0
    for name, partner_type, contact, phone, address in rows:
        partner = db.scalar(
            select(Partner).where(Partner.name == name, Partner.type == partner_type)
        )
        if partner is None:
            partner = Partner(
                name=name,
                type=partner_type,
                contact=contact,
                phone=phone,
                address=address,
                status=1,
            )
            db.add(partner)
            db.flush()
            created += 1
        partners[name] = partner
    print(f"[往来单位] 新增 {created} 个，当前共 {len(partners)} 个（2 客户 + 2 供应商）")
    return partners


def init_inventory(db: Session, skus: dict[str, ProductSku], warehouses: dict[str, Warehouse]) -> int:
    """主仓为 3 个 SKU 各写入 quantity = 100 的库存。"""
    main_warehouse = warehouses["WH001"]
    created = 0
    for sku in skus.values():
        inventory = db.scalar(
            select(Inventory).where(
                Inventory.sku_id == sku.id,
                Inventory.warehouse_id == main_warehouse.id,
            )
        )
        if inventory is None:
            db.add(
                Inventory(
                    sku_id=sku.id,
                    warehouse_id=main_warehouse.id,
                    quantity=Decimal("100.00"),
                    reserved_quantity=Decimal("0.00"),
                )
            )
            created += 1
    db.flush()
    print(f"[库存] 主仓新增 {created} 条库存记录（每个 SKU 100）")
    return created


def init_sample_order(db: Session, users: dict[str, SysUser]) -> bool:
    """1 条 status = 10 的示例待接单订单，含 2 条明细（老品行 + 新品行）。

    幂等键为单号 SAMPLE_ORDER_NO（与 sql/init_data.sql 中的 TB20260917001 一致），
    避免两条初始化路径互相不认、造出重复示例订单。

    明细按契约 17.2 的新结构写入：`sku_id` 一律留空，等仓储端「关联货号」回填。
    行 1 填了货号 SKU001（系统里真实存在，可直接匹配成功），
    行 2 未填货号且 `is_new = 1`（新品，由仓储端新建货号），两行覆盖两种分支。
    """
    exists = db.scalar(select(SalesOrder).where(SalesOrder.no == SAMPLE_ORDER_NO))
    if exists is not None:
        print(f"[示例订单] 已存在（{exists.no}），跳过")
        return False

    operator = users["operator1"]
    lines = [
        # (商品名, 货号, 是否新品, 数量, 预计成本单价)
        ("商品A", "SKU001", 0, Decimal("10"), Decimal("25.00")),
        ("新品手机壳", None, 1, Decimal("5"), Decimal("18.50")),
    ]
    total_count = sum((count for _, _, _, count, _ in lines), Decimal("0"))
    total_price = sum((count * price for _, _, _, count, price in lines), Decimal("0"))

    order = SalesOrder(
        no=SAMPLE_ORDER_NO,
        status=10,
        audit_status=0,
        remark=SAMPLE_ORDER_REMARK,
        total_count=total_count,
        total_price=total_price,
        created_by=operator.id,
    )
    db.add(order)
    db.flush()
    for product_name, sku_code, is_new, count, price in lines:
        db.add(
            SalesOrderItem(
                order_id=order.id,
                product_name=product_name,
                sku_code=sku_code,
                is_new=is_new,
                sku_id=None,  # 待仓储端关联货号
                count=count,
                out_count=Decimal("0"),
                expect_price=price,
                total_price=count * price,
            )
        )
    print(
        f"[示例订单] 新增待接单订单 {order.no}"
        f"（{len(lines)} 条明细：1 行老品填货号 + 1 行新品，金额 {total_price}）"
    )
    return True


def main() -> int:
    print(f"[配置] 数据库：{settings.DATABASE_URL}")
    print(f"[时间] 开始初始化 {datetime.now():%Y-%m-%d %H:%M:%S}")

    try:
        # 保证表已存在，脚本可单独执行
        Base.metadata.create_all(bind=engine)

        with SessionLocal() as db:
            users = init_users(db)
            warehouses = init_warehouses(db)
            skus = init_products(db)
            init_partners(db)
            init_inventory(db, skus, warehouses)
            init_sample_order(db, users)
            db.commit()
    except Exception as exc:  # noqa: BLE001
        print(f"[失败] 初始化出错：{type(exc).__name__}: {exc}", file=sys.stderr)
        print("请先执行 python3 create_tables.py，并确认 MySQL 已启动。", file=sys.stderr)
        return 1

    print("[完成] 初始化数据已写入（本脚本可重复执行，不会产生重复数据）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
