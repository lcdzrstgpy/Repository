"""库存查询与调整接口（契约 5.5 / 9.4）。"""

from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.response import BizException, normalize_page, ok, paginate
from app.core.security import require_roles
from app.models.basic import Product, ProductSku, Warehouse
from app.models.inventory import Inventory, InventoryHistory
from app.models.user import SysUser
from app.schemas.serializers import fmt_dec, inventory_history_out, inventory_out
from app.schemas.stock import InventoryAdjustIn, InventoryInboundIn
from app.services.inventory_service import (
    ORDER_TYPE_ADJUST,
    ORDER_TYPE_PURCHASE_IN,
    change_inventory,
    default_warehouse_id,
    order_type_text,
)

router = APIRouter(prefix="/api/inventory", tags=["库存查询"])

# 数量统一保留 2 位小数，四舍五入
CENT = Decimal("0.01")


def _fmt_qty(value: Decimal) -> str:
    """数量转展示文本，去掉多余的 0（100.00 -> 100）。"""
    return format(value.normalize(), "f")


def _history_out(
    record: InventoryHistory,
    sku: ProductSku | None,
    product: Product | None,
    warehouse: Warehouse | None,
    created_by_name: str | None = None,
) -> dict:
    """库存流水序列化：在统一序列化器基础上补齐契约 9.4 的两个字段。"""
    data = inventory_history_out(record, sku, product, warehouse)
    data["order_type_text"] = order_type_text(record.order_type)
    data["created_by_name"] = created_by_name
    return data


@router.get("", summary="库存列表")
def list_inventory(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1),
    keyword: str | None = Query(None, description="SKU 编码 / 商品名称 / 规格"),
    db: Session = Depends(get_db),
    _current_user: SysUser = Depends(require_roles("warehouse")),
):
    """库存余额列表，available_quantity = quantity - reserved_quantity。"""
    page, page_size = normalize_page(page, page_size)

    warehouse_id = default_warehouse_id(db)
    inventory_join = and_(ProductSku.id == Inventory.sku_id, Inventory.warehouse_id == warehouse_id)
    joins = (
        select(ProductSku, Product, Inventory, Warehouse)
        .outerjoin(Product, Product.id == ProductSku.product_id)
        .outerjoin(Inventory, inventory_join)
        .outerjoin(Warehouse, Warehouse.id == Inventory.warehouse_id)
    )
    count_stmt = (
        select(func.count())
        .select_from(ProductSku)
        .outerjoin(Product, Product.id == ProductSku.product_id)
        .outerjoin(Inventory, inventory_join)
    )

    conditions = []
    kw = (keyword or "").strip()
    if kw:
        pattern = f"%{kw}%"
        conditions.append(
            or_(
                ProductSku.sku_code.like(pattern),
                ProductSku.spec.like(pattern),
                Product.name.like(pattern),
            )
        )
    if conditions:
        joins = joins.where(*conditions)
        count_stmt = count_stmt.where(*conditions)

    total = db.scalar(count_stmt) or 0
    rows = db.execute(
        joins.order_by(ProductSku.id.asc(), Inventory.id.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    items = [
        inventory_out(inventory, sku, product, warehouse)
        if inventory is not None
        else {
            "id": None,
            "sku_id": sku.id,
            "sku_code": sku.sku_code,
            "sku_status": int(sku.status),
            "product_name": product.name if product else None,
            "spec": sku.spec,
            "quantity": 0.0,
            "reserved_quantity": 0.0,
            "available_quantity": 0.0,
        }
        for sku, product, inventory, warehouse in rows
    ]
    return ok(paginate(items, total, page, page_size))


@router.get("/alerts", summary="库存预警（安全库存）")
def list_inventory_alerts(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1),
    db: Session = Depends(get_db),
    _current_user: SysUser = Depends(require_roles("warehouse")),
):
    """库存预警：SKU 设了安全库存（min_stock > 0）且可用量低于安全库存。

    available_quantity = quantity - reserved_quantity，短缺量 = min_stock - available_quantity（恒 > 0），
    按短缺量从大到小排序。只读接口，不产生任何库存变更。
    """
    page, page_size = normalize_page(page, page_size)

    warehouse_id = default_warehouse_id(db)
    inventory_join = and_(ProductSku.id == Inventory.sku_id, Inventory.warehouse_id == warehouse_id)

    available = func.coalesce(Inventory.quantity, 0) - func.coalesce(Inventory.reserved_quantity, 0)
    shortage = ProductSku.min_stock - available
    conditions = [ProductSku.min_stock > 0, available < ProductSku.min_stock]

    joins = (
        select(ProductSku, Product, Inventory, Warehouse)
        .outerjoin(Product, Product.id == ProductSku.product_id)
        .outerjoin(Inventory, inventory_join)
        .outerjoin(Warehouse, Warehouse.id == Inventory.warehouse_id)
    )
    count_stmt = (
        select(func.count())
        .select_from(ProductSku)
        .outerjoin(Inventory, inventory_join)
        .where(*conditions)
    )

    total = db.scalar(count_stmt) or 0
    rows = db.execute(
        joins.where(*conditions)
        .order_by(shortage.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()

    items = []
    for sku, product, inventory, warehouse in rows:
        available_qty = (
            (inventory.quantity or Decimal("0")) - (inventory.reserved_quantity or Decimal("0"))
            if inventory is not None
            else Decimal("0")
        )
        data = (
            inventory_out(inventory, sku, product, warehouse)
            if inventory is not None
            else {
                "id": None,
                "sku_id": sku.id,
                "sku_code": sku.sku_code,
                "sku_status": int(sku.status),
                "product_name": product.name if product else None,
                "spec": sku.spec,
                "quantity": 0.0,
                "reserved_quantity": 0.0,
                "available_quantity": 0.0,
            }
        )
        min_stock = sku.min_stock or Decimal("0")
        data["min_stock"] = fmt_dec(min_stock)
        data["shortage"] = fmt_dec(min_stock - available_qty)
        items.append(data)
    return ok(paginate(items, total, page, page_size))


@router.get("/history", summary="库存流水")
def list_inventory_history(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1),
    sku_id: int | None = Query(None, description="按 SKU 筛选"),
    db: Session = Depends(get_db),
    _current_user: SysUser = Depends(require_roles("warehouse")),
):
    """库存流水列表。"""
    page, page_size = normalize_page(page, page_size)

    conditions = []
    if sku_id is not None:
        conditions.append(InventoryHistory.sku_id == sku_id)
    conditions.append(InventoryHistory.warehouse_id == default_warehouse_id(db))

    total = db.scalar(
        select(func.count()).select_from(InventoryHistory).where(*conditions)
    ) or 0
    rows = db.scalars(
        select(InventoryHistory)
        .where(*conditions)
        .order_by(InventoryHistory.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()

    # 批量取关联名称
    sku_ids = {r.sku_id for r in rows if r.sku_id}
    warehouse_ids = {r.warehouse_id for r in rows if r.warehouse_id}
    user_ids = {r.created_by for r in rows if r.created_by}
    skus = (
        {s.id: s for s in db.scalars(select(ProductSku).where(ProductSku.id.in_(sku_ids)))}
        if sku_ids
        else {}
    )
    product_ids = {s.product_id for s in skus.values()}
    products = (
        {p.id: p for p in db.scalars(select(Product).where(Product.id.in_(product_ids)))}
        if product_ids
        else {}
    )
    warehouses = (
        {w.id: w for w in db.scalars(select(Warehouse).where(Warehouse.id.in_(warehouse_ids)))}
        if warehouse_ids
        else {}
    )
    users = (
        {
            u.id: (u.real_name or u.username)
            for u in db.scalars(select(SysUser).where(SysUser.id.in_(user_ids)))
        }
        if user_ids
        else {}
    )

    items = [
        _history_out(
            record,
            skus.get(record.sku_id),
            products.get(skus[record.sku_id].product_id) if record.sku_id in skus else None,
            warehouses.get(record.warehouse_id),
            users.get(record.created_by),
        )
        for record in rows
    ]
    return ok(paginate(items, total, page, page_size))


@router.post("/adjust", summary="手动调整库存")
def adjust_inventory(
    payload: InventoryAdjustIn,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(require_roles("warehouse")),
):
    """仓储和管理员可调整库存；`quantity` 是目标值，后端算出差异后走库存流水。"""
    sku = db.get(ProductSku, payload.sku_id)
    if sku is None:
        raise BizException("SKU 不存在")
    warehouse_id = default_warehouse_id(db)
    warehouse = db.get(Warehouse, warehouse_id)

    inventory = db.scalar(
        select(Inventory).where(
            Inventory.sku_id == payload.sku_id,
            Inventory.warehouse_id == warehouse_id,
        )
    )
    before = Decimal(inventory.quantity or 0) if inventory is not None else Decimal("0.00")
    target = Decimal(payload.quantity).quantize(CENT, rounding=ROUND_HALF_UP)
    diff = target - before

    if diff != 0:
        change_inventory(
            db,
            [
                {
                    "sku_id": payload.sku_id,
                    "warehouse_id": warehouse_id,
                    "quantity": diff,
                }
            ],
            # 调整单没有业务单号，用时间戳生成一个便于追溯的编号
            "ADJ" + datetime.now().strftime("%Y%m%d%H%M%S"),
            ORDER_TYPE_ADJUST,
            current_user.id,
            # 调整备注写入库存流水，保证库存修正可追溯（契约 9.4）
            remark=payload.remark,
        )
        db.commit()
        # 库存行可能是刚才由 change_inventory 懒创建的，重新查一次拿到最新值
        inventory = db.scalar(
            select(Inventory).where(
                Inventory.sku_id == payload.sku_id,
                Inventory.warehouse_id == warehouse_id,
            )
        )

    product = db.get(Product, sku.product_id) if sku.product_id else None
    data = inventory_out(inventory, sku, product, warehouse) if inventory is not None else None
    return ok(
        data,
        msg=(
            f"库存已调整：{sku.sku_code} 在{warehouse.name} "
            f"由 {_fmt_qty(before)} 变为 {_fmt_qty(target)}"
        ),
    )


@router.post("/inbound", summary="采购入库")
def inbound_inventory(
    payload: InventoryInboundIn,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(require_roles("warehouse")),
):
    """仓储录入采购或提前备货数量，并写入采购入库库存流水。"""
    sku = db.get(ProductSku, payload.sku_id)
    if sku is None:
        raise BizException("货号不存在")
    if sku.status != 1:
        raise BizException("货号已停用，无法采购入库")
    warehouse_id = default_warehouse_id(db)
    warehouse = db.get(Warehouse, warehouse_id)

    quantity = Decimal(payload.quantity)
    change_inventory(
        db,
        [{"sku_id": sku.id, "warehouse_id": warehouse_id, "quantity": quantity}],
        "PIN" + datetime.now().strftime("%Y%m%d%H%M%S%f"),
        ORDER_TYPE_PURCHASE_IN,
        current_user.id,
        remark=payload.remark,
    )
    db.commit()
    return ok(msg=f"已入库：{sku.sku_code} +{_fmt_qty(quantity)}")
