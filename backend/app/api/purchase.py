"""采购接口（契约 10.3）：采购单创建 / 列表 / 详情 / 审批 / 取消 / 收货入库，入库单列表 / 详情。

设计要点（契约 10.1）：采购单本身不影响库存，只有「收货入库」才通过
`change_inventory` 增加库存；库存变更与入库单、明细 in_count 在同一事务里提交。
"""

from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.response import BizException, NotFoundException, normalize_page, ok, paginate
from app.core.security import require_roles
from app.models.basic import Partner, Product, ProductSku, Warehouse
from app.models.order import SalesOrder
from app.models.purchase import (
    PURCHASE_IN_STATUS_DONE,
    PURCHASE_STATUS_APPROVED,
    PURCHASE_STATUS_CANCELLED,
    PURCHASE_STATUS_PENDING,
    PURCHASE_STATUS_RECEIVED,
    PurchaseIn,
    PurchaseInItem,
    PurchaseOrder,
    PurchaseOrderItem,
    purchase_status_text,
)
from app.models.user import SysUser
from app.schemas.purchase import (
    PurchaseOrderCreateIn,
    PurchaseReceiveIn,
    purchase_in_brief,
    purchase_in_detail,
    purchase_in_item_out,
    purchase_order_brief,
    purchase_order_detail,
    purchase_order_item_out,
)
from app.services.inventory_service import ORDER_TYPE_PURCHASE_IN, change_inventory

router = APIRouter(prefix="/api/purchase-orders", tags=["仓储侧·采购单"])
purchase_in_router = APIRouter(prefix="/api/purchase-ins", tags=["仓储侧·采购入库单"])

# 金额 / 数量统一保留 2 位小数，四舍五入
CENT = Decimal("0.01")


# ---------------------------------------------------------------- 通用工具
def get_purchase_order_or_404(db: Session, order_id: int) -> PurchaseOrder:
    """按 id 取采购单，不存在抛 404。"""
    order = db.get(PurchaseOrder, order_id)
    if order is None:
        raise NotFoundException("采购单不存在")
    return order


def _fmt_qty(value: Decimal) -> str:
    """数量转展示文本，去掉多余的 0（50.00 -> 50）。"""
    return format(value.quantize(CENT, rounding=ROUND_HALF_UP).normalize(), "f")


def _name_maps(
    db: Session, orders: list[PurchaseOrder]
) -> tuple[dict, dict, dict]:
    """批量取供应商名、用户名、销售订单号，避免逐行查询。"""
    supplier_ids = {o.supplier_id for o in orders if o.supplier_id}
    user_ids = {o.created_by for o in orders if o.created_by}
    user_ids |= {o.approved_by for o in orders if o.approved_by}
    sales_order_ids = {o.sales_order_id for o in orders if o.sales_order_id}

    suppliers = (
        {p.id: p.name for p in db.scalars(select(Partner).where(Partner.id.in_(supplier_ids)))}
        if supplier_ids
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
    sales_orders = (
        {
            o.id: o.no
            for o in db.scalars(select(SalesOrder).where(SalesOrder.id.in_(sales_order_ids)))
        }
        if sales_order_ids
        else {}
    )
    return suppliers, users, sales_orders


def build_purchase_order_briefs(db: Session, orders: list[PurchaseOrder]) -> list[dict]:
    """采购单列表元素批量序列化（契约 10.3 列表）。"""
    if not orders:
        return []
    suppliers, users, sales_orders = _name_maps(db, orders)
    return [
        purchase_order_brief(
            order,
            supplier_name=suppliers.get(order.supplier_id),
            sales_order_no=sales_orders.get(order.sales_order_id),
            created_by_name=users.get(order.created_by),
            approved_by_name=users.get(order.approved_by),
        )
        for order in orders
    ]


def build_purchase_order_detail(db: Session, order: PurchaseOrder) -> dict:
    """采购单详情序列化（契约 10.3 详情，含明细）。"""
    suppliers, users, sales_orders = _name_maps(db, [order])
    items = list(
        db.scalars(
            select(PurchaseOrderItem)
            .where(PurchaseOrderItem.order_id == order.id)
            .order_by(PurchaseOrderItem.id.asc())
        )
    )
    skus, products = _load_sku_maps(db, {item.sku_id for item in items})
    item_dicts = [
        purchase_order_item_out(
            item,
            skus.get(item.sku_id),
            products.get(skus[item.sku_id].product_id) if item.sku_id in skus else None,
        )
        for item in items
    ]
    return purchase_order_detail(
        order,
        supplier_name=suppliers.get(order.supplier_id),
        sales_order_no=sales_orders.get(order.sales_order_id),
        created_by_name=users.get(order.created_by),
        approved_by_name=users.get(order.approved_by),
        items=item_dicts,
    )


def _load_sku_maps(
    db: Session, sku_ids: set[int]
) -> tuple[dict[int, ProductSku], dict[int, Product]]:
    """批量取 SKU 与所属商品。"""
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
    return skus, products


# ---------------------------------------------------------------- 单号生成
def generate_purchase_order_no(db: Session) -> str:
    """生成单号：PO + yyyyMMdd + 4 位当日流水，如 PO202609160001。"""
    prefix = "PO" + datetime.now().strftime("%Y%m%d")
    max_no = db.scalar(select(func.max(PurchaseOrder.no)).where(PurchaseOrder.no.like(f"{prefix}%")))
    seq = 1
    if max_no:
        try:
            seq = int(str(max_no)[-4:]) + 1
        except ValueError:
            seq = 1
    return f"{prefix}{seq:04d}"


def generate_purchase_in_no(db: Session) -> str:
    """生成单号：IN + yyyyMMdd + 4 位当日流水，如 IN202609160001。"""
    prefix = "IN" + datetime.now().strftime("%Y%m%d")
    max_no = db.scalar(select(func.max(PurchaseIn.no)).where(PurchaseIn.no.like(f"{prefix}%")))
    seq = 1
    if max_no:
        try:
            seq = int(str(max_no)[-4:]) + 1
        except ValueError:
            seq = 1
    return f"{prefix}{seq:04d}"


# ---------------------------------------------------------------- 采购单接口
@router.post("", summary="创建采购单")
def create_purchase_order(
    payload: PurchaseOrderCreateIn,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(require_roles("warehouse", "admin")),
):
    """创建采购单。created_by 取当前用户，status 固定 10，总额由后端汇总。

    采购单不碰库存，只有收货入库才增加库存（契约 10.1）。
    """
    # 校验供应商：partner.type 必须含 2
    supplier = db.get(Partner, payload.supplier_id)
    if supplier is None:
        raise BizException("供应商不存在")
    if supplier.type not in (2, 3):
        raise BizException(f"往来单位「{supplier.name}」不是供应商，不能用于采购")

    # 关联销售订单（可选）必须存在
    if payload.sales_order_id is not None and db.get(SalesOrder, payload.sales_order_id) is None:
        raise BizException(f"关联销售订单(id={payload.sales_order_id})不存在")

    # 校验 SKU
    sku_ids = [item.sku_id for item in payload.items]
    sku_map = {s.id: s for s in db.scalars(select(ProductSku).where(ProductSku.id.in_(sku_ids)))}
    for sku_id in sku_ids:
        sku = sku_map.get(sku_id)
        if sku is None:
            raise BizException(f"SKU(id={sku_id})不存在")
        if sku.status != 1:
            raise BizException(f"SKU「{sku.sku_code}」已停用，无法采购")

    # 后端汇总总额，不信任前端传值
    total_count = sum((item.count for item in payload.items), Decimal("0"))
    total_price = sum(
        ((item.count * item.price).quantize(CENT, rounding=ROUND_HALF_UP) for item in payload.items),
        Decimal("0"),
    )

    # purchase_order.no 有唯一索引：并发下可能撞号，捕获后重试
    order: PurchaseOrder | None = None
    for _ in range(5):
        try:
            order = PurchaseOrder(
                no=generate_purchase_order_no(db),
                supplier_id=payload.supplier_id,
                sales_order_id=payload.sales_order_id,
                status=PURCHASE_STATUS_PENDING,
                total_count=total_count,
                total_price=total_price,
                expect_date=payload.expect_date,
                remark=payload.remark,
                created_by=current_user.id,
            )
            db.add(order)
            db.flush()
            for item in payload.items:
                db.add(
                    PurchaseOrderItem(
                        order_id=order.id,
                        sku_id=item.sku_id,
                        count=item.count,
                        in_count=Decimal("0"),
                        price=item.price,
                        total_price=(item.count * item.price).quantize(
                            CENT, rounding=ROUND_HALF_UP
                        ),
                    )
                )
            db.commit()
            break
        except IntegrityError:
            db.rollback()
            order = None
    if order is None:
        raise BizException("采购单号生成冲突，请稍后重试")

    db.refresh(order)
    return ok(build_purchase_order_detail(db, order), msg="采购单创建成功")


@router.get("", summary="采购单列表")
def list_purchase_orders(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1),
    status: int | None = Query(None, description="采购单状态"),
    keyword: str | None = Query(None, description="单号 / 供应商名称 / 销售订单号"),
    db: Session = Depends(get_db),
    _current_user: SysUser = Depends(require_roles("warehouse", "approver", "admin")),
):
    """采购单列表，支持 ?page=&page_size=&status=&keyword=。"""
    page, page_size = normalize_page(page, page_size)

    conditions = []
    if status is not None:
        conditions.append(PurchaseOrder.status == status)
    kw = (keyword or "").strip()

    stmt = (
        select(PurchaseOrder)
        .outerjoin(Partner, Partner.id == PurchaseOrder.supplier_id)
        .outerjoin(SalesOrder, SalesOrder.id == PurchaseOrder.sales_order_id)
    )
    count_stmt = (
        select(func.count())
        .select_from(PurchaseOrder)
        .outerjoin(Partner, Partner.id == PurchaseOrder.supplier_id)
        .outerjoin(SalesOrder, SalesOrder.id == PurchaseOrder.sales_order_id)
    )
    if kw:
        pattern = f"%{kw}%"
        condition = or_(
            PurchaseOrder.no.like(pattern),
            Partner.name.like(pattern),
            SalesOrder.no.like(pattern),
        )
        stmt = stmt.where(condition)
        count_stmt = count_stmt.where(condition)
    if conditions:
        stmt = stmt.where(*conditions)
        count_stmt = count_stmt.where(*conditions)

    total = db.scalar(count_stmt) or 0
    rows = db.scalars(
        stmt.order_by(PurchaseOrder.id.desc()).offset((page - 1) * page_size).limit(page_size)
    ).all()
    return ok(paginate(build_purchase_order_briefs(db, list(rows)), total, page, page_size))


@router.get("/{order_id}", summary="采购单详情")
def get_purchase_order(
    order_id: int,
    db: Session = Depends(get_db),
    _current_user: SysUser = Depends(require_roles("warehouse", "approver", "admin")),
):
    """采购单详情，含明细。"""
    order = get_purchase_order_or_404(db, order_id)
    return ok(build_purchase_order_detail(db, order))


@router.post("/{order_id}/approve", summary="审批采购单")
def approve_purchase_order(
    order_id: int,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(require_roles("approver", "admin")),
):
    """审批通过：status 10 → 20，写 approved_by / approved_at。审批不影响库存。"""
    order = get_purchase_order_or_404(db, order_id)
    if order.status != PURCHASE_STATUS_PENDING:
        raise BizException(
            f"采购单当前状态为「{purchase_status_text(order.status)}」，无法执行审批操作"
        )

    order.status = PURCHASE_STATUS_APPROVED
    order.approved_by = current_user.id
    order.approved_at = datetime.now()
    db.commit()
    db.refresh(order)
    return ok(build_purchase_order_detail(db, order), msg="审批通过")


@router.post("/{order_id}/cancel", summary="取消采购单")
def cancel_purchase_order(
    order_id: int,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(require_roles("warehouse", "admin")),
):
    """取消采购单：status 10 / 20 可取消，改为 90；已有入库记录则不允许取消。"""
    order = get_purchase_order_or_404(db, order_id)
    if order.status not in (PURCHASE_STATUS_PENDING, PURCHASE_STATUS_APPROVED):
        raise BizException(
            f"采购单当前状态为「{purchase_status_text(order.status)}」，无法执行取消操作"
        )

    received = db.scalar(
        select(func.count())
        .select_from(PurchaseOrderItem)
        .where(PurchaseOrderItem.order_id == order.id, PurchaseOrderItem.in_count > 0)
    )
    if received:
        raise BizException("采购单已有入库记录，无法取消")

    order.status = PURCHASE_STATUS_CANCELLED
    db.commit()
    db.refresh(order)
    return ok(build_purchase_order_detail(db, order), msg="采购单已取消")


@router.post("/{order_id}/receive", summary="收货入库")
def receive_purchase_order(
    order_id: int,
    payload: PurchaseReceiveIn,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(require_roles("warehouse", "admin")),
):
    """收货入库（契约 10.3 六步）。

    1. 校验采购单 status = 20
    2. 校验明细归属与本次入库量不超过 count - in_count
    3. change_inventory 增加库存（正数）
    4. 生成 purchase_in（status = 20）+ purchase_in_item
    5. 回写 purchase_order_item.in_count
    6. 所有明细 in_count == count 时，采购单 status → 30
    7. 统一 commit（库存、入库单、in_count 同事务）
    """
    order = get_purchase_order_or_404(db, order_id)

    # 步骤 1：仅「已审批」可收货入库
    if order.status != PURCHASE_STATUS_APPROVED:
        raise BizException(
            f"采购单当前状态为「{purchase_status_text(order.status)}」，无法执行收货入库操作"
        )

    warehouse = db.get(Warehouse, payload.warehouse_id)
    if warehouse is None:
        raise BizException("入库仓库不存在")

    # 步骤 2：明细必须属于该采购单，且本次入库量 > 0 且不超过剩余可入库量
    order_items = {
        item.id: item
        for item in db.scalars(
            select(PurchaseOrderItem).where(PurchaseOrderItem.order_id == order.id)
        )
    }
    if not order_items:
        raise BizException("采购单没有明细，无法收货入库")

    lines: list[tuple[PurchaseOrderItem, Decimal]] = []
    for line in payload.items:
        item = order_items.get(line.order_item_id)
        if item is None:
            raise BizException(f"采购明细(id={line.order_item_id})不属于该采购单")
        count = Decimal(line.count).quantize(CENT, rounding=ROUND_HALF_UP)
        remain = (Decimal(item.count or 0) - Decimal(item.in_count or 0)).quantize(
            CENT, rounding=ROUND_HALF_UP
        )
        if count > remain:
            raise BizException(
                f"SKU(id={item.sku_id}) 本次入库量 {_fmt_qty(count)} "
                f"超出剩余可入库量 {_fmt_qty(remain)}"
            )
        lines.append((item, count))

    in_no = generate_purchase_in_no(db)
    total_count = sum((count for _, count in lines), Decimal("0"))
    total_price = sum(
        (
            (count * Decimal(item.price or 0)).quantize(CENT, rounding=ROUND_HALF_UP)
            for item, count in lines
        ),
        Decimal("0"),
    )

    try:
        # 步骤 3：走统一库存服务增加库存（正数入库），本函数内部不 commit
        change_inventory(
            db,
            [
                {
                    "sku_id": item.sku_id,
                    "warehouse_id": payload.warehouse_id,
                    "quantity": count,
                }
                for item, count in lines
            ],
            in_no,
            ORDER_TYPE_PURCHASE_IN,
            current_user.id,
        )

        # 步骤 4：生成采购入库单（创建即已完成）+ 入库明细
        in_record = PurchaseIn(
            no=in_no,
            order_id=order.id,
            order_no=order.no,
            warehouse_id=payload.warehouse_id,
            status=PURCHASE_IN_STATUS_DONE,
            total_count=total_count,
            total_price=total_price,
            remark=payload.remark,
            created_by=current_user.id,
        )
        db.add(in_record)
        db.flush()
        for item, count in lines:
            db.add(
                PurchaseInItem(
                    in_id=in_record.id,
                    order_item_id=item.id,
                    sku_id=item.sku_id,
                    count=count,
                    price=item.price,
                    total_price=(count * Decimal(item.price or 0)).quantize(
                        CENT, rounding=ROUND_HALF_UP
                    ),
                )
            )

        # 步骤 5：回写采购明细的已入库数量
        for item, count in lines:
            item.in_count = (Decimal(item.in_count or 0) + count).quantize(
                CENT, rounding=ROUND_HALF_UP
            )
        db.flush()

        # 步骤 6：全部明细入库完毕，采购单转「已入库」
        if all(
            Decimal(item.in_count or 0) >= Decimal(item.count or 0)
            for item in order_items.values()
        ):
            order.status = PURCHASE_STATUS_RECEIVED

        # 步骤 7：统一提交
        db.commit()
    except IntegrityError:
        # 入库单号撞号等：整单回滚（库存变更、入库单、in_count 一起撤销）
        db.rollback()
        raise BizException("入库单号生成冲突，请稍后重试")

    db.refresh(order)
    return ok(build_purchase_order_detail(db, order), msg=f"收货入库成功，入库单号 {in_no}")


# ---------------------------------------------------------------- 入库单接口
def _load_purchase_in_names(
    db: Session, rows: list[PurchaseIn]
) -> tuple[dict, dict]:
    """批量取仓库名与操作人姓名。"""
    warehouse_ids = {r.warehouse_id for r in rows if r.warehouse_id}
    user_ids = {r.created_by for r in rows if r.created_by}
    warehouses = (
        {w.id: w.name for w in db.scalars(select(Warehouse).where(Warehouse.id.in_(warehouse_ids)))}
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
    return warehouses, users


def build_purchase_in_briefs(db: Session, rows: list[PurchaseIn]) -> list[dict]:
    """入库单列表元素批量序列化。"""
    if not rows:
        return []
    warehouses, users = _load_purchase_in_names(db, rows)
    return [
        purchase_in_brief(
            row,
            warehouse_name=warehouses.get(row.warehouse_id),
            created_by_name=users.get(row.created_by),
        )
        for row in rows
    ]


def build_purchase_in_detail(db: Session, purchase_in: PurchaseIn) -> dict:
    """入库单详情序列化，含明细。"""
    warehouses, users = _load_purchase_in_names(db, [purchase_in])
    items = list(
        db.scalars(
            select(PurchaseInItem)
            .where(PurchaseInItem.in_id == purchase_in.id)
            .order_by(PurchaseInItem.id.asc())
        )
    )
    skus, products = _load_sku_maps(db, {item.sku_id for item in items})
    item_dicts = [
        purchase_in_item_out(
            item,
            skus.get(item.sku_id),
            products.get(skus[item.sku_id].product_id) if item.sku_id in skus else None,
        )
        for item in items
    ]
    return purchase_in_detail(
        purchase_in,
        warehouse_name=warehouses.get(purchase_in.warehouse_id),
        created_by_name=users.get(purchase_in.created_by),
        items=item_dicts,
    )


@purchase_in_router.get("", summary="入库单列表")
def list_purchase_ins(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1),
    keyword: str | None = Query(None, description="入库单号 / 采购单号"),
    db: Session = Depends(get_db),
    _current_user: SysUser = Depends(require_roles("warehouse", "admin")),
):
    """采购入库单列表。"""
    page, page_size = normalize_page(page, page_size)

    stmt = select(PurchaseIn)
    count_stmt = select(func.count()).select_from(PurchaseIn)
    kw = (keyword or "").strip()
    if kw:
        pattern = f"%{kw}%"
        condition = or_(PurchaseIn.no.like(pattern), PurchaseIn.order_no.like(pattern))
        stmt = stmt.where(condition)
        count_stmt = count_stmt.where(condition)

    total = db.scalar(count_stmt) or 0
    rows = db.scalars(
        stmt.order_by(PurchaseIn.id.desc()).offset((page - 1) * page_size).limit(page_size)
    ).all()
    return ok(paginate(build_purchase_in_briefs(db, list(rows)), total, page, page_size))


@purchase_in_router.get("/{in_id}", summary="入库单详情")
def get_purchase_in(
    in_id: int,
    db: Session = Depends(get_db),
    _current_user: SysUser = Depends(require_roles("warehouse", "admin")),
):
    """采购入库单详情，含明细。"""
    purchase_in = db.get(PurchaseIn, in_id)
    if purchase_in is None:
        raise NotFoundException("入库单不存在")
    return ok(build_purchase_in_detail(db, purchase_in))


def register_purchase_routers(app) -> None:
    """把采购单与入库单两组路由挂到应用上。"""
    for item in (router, purchase_in_router):
        app.include_router(item)
