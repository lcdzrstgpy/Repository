"""运营侧订单接口（契约 5.3）：下单、列表、详情、取消、确认完成。"""

import logging
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.response import (
    BizException,
    ForbiddenException,
    NotFoundException,
    normalize_page,
    ok,
    paginate,
)
from app.core.security import require_roles
from app.models.basic import Partner, Product, ProductCategory, ProductSku, Warehouse
from app.models.order import (
    ORDER_STATUS_CLAIMED,
    ORDER_STATUS_PENDING,
    ORDER_STATUS_PREPARING,
    ORDER_STATUS_PARTIALLY_SHIPPED,
    SalesOrder,
    SalesOrderItem,
    ensure_transition,
)
from app.models.user import SysUser
from app.models.stock import SalesOut, SalesOutItem
from app.models.inventory import InventoryHistory
from app.schemas.order import SalesOrderCancelIn, SalesOrderCreateIn
from app.schemas.serializers import order_brief, order_detail, order_item_out
from app.services.inventory_service import release_inventory

router = APIRouter(prefix="/api/sales-orders", tags=["运营侧·订单"])

logger = logging.getLogger(__name__)

# 金额统一保留 2 位小数，四舍五入
CENT = Decimal("0.01")


# ---------------------------------------------------------------- 通用工具


def get_order_or_404(db: Session, order_id: int, for_update: bool = False) -> SalesOrder:
    """按 id 取订单，不存在抛 404。

    :param for_update: 是否对订单行加悲观锁（`SELECT ... FOR UPDATE`）。
        接单 / 发货 / 取消这类「读状态 → 校验 → 改状态」的写操作必须传 True，
        否则并发下两次请求都会读到旧状态、都通过校验，造成重复接单 / 重复发货。
    """
    if for_update:
        order = db.scalars(
            select(SalesOrder).where(SalesOrder.id == order_id).with_for_update()
        ).first()
    else:
        order = db.get(SalesOrder, order_id)
    if order is None:
        raise NotFoundException("订单不存在")
    return order


def ensure_visible(order: SalesOrder, current_user: SysUser) -> None:
    """可见性规则：operator 只能操作自己创建的订单。"""
    if current_user.role == "operator" and order.created_by != current_user.id:
        raise ForbiddenException("无权操作他人创建的订单")


def _name_maps(db: Session, orders: list[SalesOrder]) -> tuple[dict, dict, dict]:
    """批量取客户名、用户名、仓库名，避免逐行查询。"""
    customer_ids = {o.customer_id for o in orders if o.customer_id}
    user_ids = {o.created_by for o in orders if o.created_by}
    user_ids |= {o.claimed_by for o in orders if o.claimed_by}
    warehouse_ids = {o.warehouse_id for o in orders if o.warehouse_id}

    customers = (
        {p.id: p.name for p in db.scalars(select(Partner).where(Partner.id.in_(customer_ids)))}
        if customer_ids
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
    warehouses = (
        {w.id: w.name for w in db.scalars(select(Warehouse).where(Warehouse.id.in_(warehouse_ids)))}
        if warehouse_ids
        else {}
    )
    return customers, users, warehouses


def build_order_briefs(db: Session, orders: list[SalesOrder]) -> list[dict]:
    """订单列表元素批量序列化（契约 5.3 列表）。"""
    if not orders:
        return []
    customers, users, _ = _name_maps(db, orders)
    result = []
    for order in orders:
        row = order_brief(order, customer_name=customers.get(order.customer_id), created_by_name=users.get(order.created_by), claimed_by_name=users.get(order.claimed_by))
        detail = build_order_detail(db, order)
        item = detail["items"][0] if detail["items"] else {}
        row.update({"product_name": item.get("product_name"), "item_no": item.get("item_no"), "image_url": item.get("image_url"), "remark": order.remark, "estimated_cost": float(order.total_price or 0)})
        result.append(row)
    return result


def build_order_detail(db: Session, order: SalesOrder) -> dict:
    """订单详情序列化（契约 5.3 详情，含明细）。"""
    customers, users, warehouses = _name_maps(db, [order])
    items = list(order.items)
    sku_ids = [item.sku_id for item in items]
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
    item_dicts = [
        order_item_out(
            item,
            skus.get(item.sku_id),
            products.get(skus[item.sku_id].product_id) if item.sku_id in skus else None,
        )
        for item in items
    ]
    shipments = []
    for out in db.scalars(select(SalesOut).where(SalesOut.order_id == order.id).order_by(SalesOut.id.asc())).all():
        history = db.scalars(
            select(InventoryHistory)
            .where(InventoryHistory.order_no == out.no)
            .order_by(InventoryHistory.id.desc())
        ).first()
        shipments.append({
            "out_no": out.no,
            "warehouse_name": warehouses.get(out.warehouse_id),
            "express_no": out.express_no,
            "shipped_at": out.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            "count": float(out.total_count or 0),
            "stock_after": float(history.after_quantity) if history else None,
            "status": int(out.status),
        })
    data = order_detail(
        order,
        customer_name=customers.get(order.customer_id),
        created_by_name=users.get(order.created_by),
        claimed_by_name=users.get(order.claimed_by),
        warehouse_name=warehouses.get(order.warehouse_id),
        items=item_dicts,
    )
    data["shipments"] = shipments
    return data


# ---------------------------------------------------------------- 库存预留


def build_order_outbound_changes(order: SalesOrder, warehouse_id: int) -> list[dict]:
    """按订单明细的剩余待出量构造库存变更明细（负数，出库方向）。

    四阶段的「接单预留 / 发货释放 / 取消释放」三处共用同一个构造方式，
    保证预留的量与释放的量永远一致。数量为 0 的明细直接跳过。
    """
    changes: list[dict] = []
    for item in order.items:
        count = Decimal(item.count or 0) - Decimal(item.out_count or 0)
        if count > 0:
            changes.append(
                {"sku_id": item.sku_id, "warehouse_id": warehouse_id, "quantity": -count}
            )
    return changes


# ---------------------------------------------------------------- 单号生成


def generate_order_no(db: Session) -> str:
    """生成单号：SO + yyyyMMdd + 4 位当日流水，如 SO202609160001。"""
    prefix = "SO" + datetime.now().strftime("%Y%m%d")
    max_no = db.scalar(select(func.max(SalesOrder.no)).where(SalesOrder.no.like(f"{prefix}%")))
    seq = 1
    if max_no:
        try:
            seq = int(str(max_no)[-4:]) + 1
        except ValueError:
            seq = 1
    return f"{prefix}{seq:04d}"


def _category_segment(level: int, sequence: int) -> str:
    return f"{'ABC'[level - 1]}{sequence:03d}"


def resolve_new_item(db: Session, payload) -> ProductSku:
    """创建或复用运营填写的三级分类商品，并生成三段货号。"""
    parent_id = None
    categories = []
    for level, raw_name in enumerate(payload.categories, start=1):
        name = raw_name.strip()
        if not name:
            raise BizException("三级分类不能为空")
        stmt = select(ProductCategory).where(ProductCategory.level == level, ProductCategory.name == name)
        stmt = stmt.where(ProductCategory.parent_id.is_(None)) if parent_id is None else stmt.where(ProductCategory.parent_id == parent_id)
        category = db.scalars(stmt).first()
        if category is None:
            sibling_stmt = select(func.count()).select_from(ProductCategory).where(ProductCategory.level == level)
            sibling_stmt = sibling_stmt.where(ProductCategory.parent_id.is_(None)) if parent_id is None else sibling_stmt.where(ProductCategory.parent_id == parent_id)
            category = ProductCategory(parent_id=parent_id, level=level, name=name, code_segment=_category_segment(level, int(db.scalar(sibling_stmt) or 0) + 1))
            db.add(category)
            db.flush()
        categories.append(category)
        parent_id = category.id

    existing = db.scalars(
        select(ProductSku).join(Product, Product.id == ProductSku.product_id).where(
            ProductSku.category_id == categories[-1].id,
            Product.name == payload.product_name.strip(),
            ProductSku.spec == (payload.spec or None),
        )
    ).first()
    if existing:
        return existing
    product = Product(code=f"P{datetime.now().strftime('%Y%m%d%H%M%S%f')}", name=payload.product_name.strip(), status=1)
    db.add(product)
    db.flush()
    item_no = "-".join(category.code_segment for category in categories)
    sku = ProductSku(product_id=product.id, category_id=categories[-1].id, sku_code=item_no, spec=payload.spec, image_url=payload.image_url, remark=payload.item_remark, price=Decimal("0"), min_stock=Decimal("0"), status=1)
    db.add(sku)
    db.flush()
    return sku


# ---------------------------------------------------------------- 接口


@router.post("", summary="创建订单")
def create_order(
    payload: SalesOrderCreateIn,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(require_roles("operator", "admin")),
):
    """运营下单：一张店小秘订单只对应一个货号。"""
    if bool(payload.sku_code) == bool(payload.new_item):
        raise BizException("请选择已有货号，或填写无货号商品资料（二选一）")
    sku = (
        db.scalars(select(ProductSku).where(ProductSku.sku_code == payload.sku_code.strip())).first()
        if payload.sku_code else resolve_new_item(db, payload.new_item)
    )
    if sku is None or sku.status != 1:
        raise BizException("货号不存在或已停用")

    # sales_order.no 有唯一索引：并发下可能撞号，捕获后重试
    order: SalesOrder | None = None
    for _ in range(5):
        try:
            order = SalesOrder(
                no=payload.no.strip(),
                # 兼容已升级数据库中的旧字段；对外只使用 no。
                external_no=payload.no.strip(),
                status=ORDER_STATUS_PENDING,
                remark=payload.remark,
                total_count=payload.count,
                total_price=payload.estimated_cost,
                created_by=current_user.id,
            )
            db.add(order)
            db.flush()
            unit_cost = (payload.estimated_cost / payload.count).quantize(CENT, rounding=ROUND_HALF_UP) if payload.count else Decimal("0")
            db.add(SalesOrderItem(order_id=order.id, sku_id=sku.id, count=payload.count, out_count=Decimal("0"), price=unit_cost, total_price=payload.estimated_cost))
            db.commit()
            break
        except IntegrityError:
            db.rollback()
            order = None
    if order is None:
        raise BizException("订单号生成冲突，请稍后重试")

    db.refresh(order)
    return ok(build_order_detail(db, order), msg="下单成功")


@router.get("", summary="订单列表")
def list_orders(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1),
    status: int | None = Query(None, description="订单状态"),
    keyword: str | None = Query(None, description="单号 / 客户名 / 物流单号"),
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(require_roles("operator", "warehouse", "admin")),
):
    """订单列表。

    可见性规则：operator 只返回 created_by = 当前用户 的订单；admin / warehouse 返回全部。
    approver 无权限（契约第十一节「订单列表」为 ❌）。
    """
    page, page_size = normalize_page(page, page_size)

    conditions = []
    if current_user.role == "operator":
        conditions.append(SalesOrder.created_by == current_user.id)
    if status is not None:
        conditions.append(SalesOrder.status == status)
    kw = (keyword or "").strip()

    stmt = select(SalesOrder).outerjoin(Partner, Partner.id == SalesOrder.customer_id)
    count_stmt = select(func.count()).select_from(SalesOrder).outerjoin(
        Partner, Partner.id == SalesOrder.customer_id
    )
    if kw:
        pattern = f"%{kw}%"
        condition = or_(
            SalesOrder.no.like(pattern),
            SalesOrder.express_no.like(pattern),
            Partner.name.like(pattern),
            SalesOrder.external_no.like(pattern),
        )
        stmt = stmt.where(condition)
        count_stmt = count_stmt.where(condition)
    if conditions:
        stmt = stmt.where(*conditions)
        count_stmt = count_stmt.where(*conditions)

    total = db.scalar(count_stmt) or 0
    rows = db.scalars(
        stmt.order_by(SalesOrder.id.desc()).offset((page - 1) * page_size).limit(page_size)
    ).all()
    return ok(paginate(build_order_briefs(db, list(rows)), total, page, page_size))


@router.get("/{order_id}", summary="订单详情")
def get_order(
    order_id: int,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(require_roles("operator", "warehouse", "admin")),
):
    """订单详情，含明细。approver 无权限（契约第十一节）。"""
    order = get_order_or_404(db, order_id)
    ensure_visible(order, current_user)
    return ok(build_order_detail(db, order))


@router.post("/{order_id}/cancel", summary="取消订单")
def cancel_order(
    order_id: int,
    payload: SalesOrderCancelIn,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(require_roles("operator", "warehouse", "admin")),
):
    """取消订单。仅 status 在 10 / 20 / 30 时可取消；operator 只能取消自己的订单。

    四阶段（契约 12.2）：订单处于「已接单(20) / 备货中(30)」时，接单那一刻已经
    预留过库存，取消要把预留释放掉；「待接单(10)」还没预留，不需要动库存。
    释放与状态变更在同一事务里提交。

    并发保护：先对订单行加 `FOR UPDATE` 锁，再读状态校验，避免并发下重复取消 / 重复释放。
    """
    # 加行锁读取：保证「读状态 → 校验 → 释放预留 → 改状态」之间没有其他事务插入
    order = get_order_or_404(db, order_id, for_update=True)
    ensure_visible(order, current_user)

    target = ensure_transition(order.status, "取消")

    # 这里必须读 order.status（此时还没被改成 target），判断的是取消前的状态
    if (
        order.status in (ORDER_STATUS_CLAIMED, ORDER_STATUS_PREPARING, ORDER_STATUS_PARTIALLY_SHIPPED)
        and order.warehouse_id is not None
    ):
        warnings = release_inventory(
            db,
            build_order_outbound_changes(order, order.warehouse_id),
            order.no,
            current_user.id,
        )
        if warnings:
            # 预留账实不符：释放量超过当前预留量，已钳制为 0。这里再记一条业务级日志，
            # 便于把「哪张订单触发了钳制」与库存服务的明细告警串起来（P2-2）。
            logger.warning(
                "取消订单时释放预留出现账实不符，已钳制为 0：order_no=%s, 明细=%s",
                order.no,
                warnings,
            )

    order.status = target
    order.cancel_reason = payload.cancel_reason
    db.commit()
    db.refresh(order)
    return ok(build_order_detail(db, order), msg="订单已取消")


@router.post("/{order_id}/confirm", summary="确认完成")
def confirm_order(
    order_id: int,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(require_roles("operator", "admin")),
):
    """确认完成。仅 status = 40 时可确认；operator 只能确认自己的订单。"""
    order = get_order_or_404(db, order_id)
    ensure_visible(order, current_user)

    target = ensure_transition(order.status, "确认完成")
    order.status = target
    order.finished_at = datetime.now()
    db.commit()
    db.refresh(order)
    return ok(build_order_detail(db, order), msg="订单已完成")
