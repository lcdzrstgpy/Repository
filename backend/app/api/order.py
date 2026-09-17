"""运营侧订单接口（契约 19，覆盖 5.3）：下单、列表、详情、确认数量、取消、确认完成。

六阶段起运营录入的是外部平台订单：请求体只有订单号 + 明细（商品名 / 货号或新品 /
数量 / 预计成本），不再有客户字段；明细的 `sku_id` 留空，由仓储端「关联货号」回填。
"""

from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import case, func, or_, select
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
from app.models.basic import ProductSku, Warehouse
from app.models.order import (
    ORDER_STATUS_PENDING,
    SalesOrder,
    SalesOrderItem,
    ensure_transition,
)
from app.models.user import SysUser
from app.schemas.order import ConfirmQuantityIn, SalesOrderCancelIn, SalesOrderCreateIn
from app.schemas.serializers import order_brief, order_detail, order_item_out

router = APIRouter(prefix="/api/sales-orders", tags=["运营侧·订单"])

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


def _name_maps(db: Session, orders: list[SalesOrder]) -> tuple[dict, dict]:
    """批量取用户名、仓库名，避免逐行查询。"""
    user_ids = {o.created_by for o in orders if o.created_by}
    user_ids |= {o.claimed_by for o in orders if o.claimed_by}
    warehouse_ids = {o.warehouse_id for o in orders if o.warehouse_id}

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
    return users, warehouses


def _item_stats(db: Session, order_ids: list[int]) -> dict[int, tuple[int, int]]:
    """批量统计订单的明细行数与未关联货号行数。

    一次 `GROUP BY` 查出整页数据，避免逐单查明细造成 N+1。
    返回 `{order_id: (item_count, unbound_count)}`，没有明细的订单不在结果里。
    """
    if not order_ids:
        return {}
    rows = db.execute(
        select(
            SalesOrderItem.order_id,
            func.count(SalesOrderItem.id),
            func.sum(case((SalesOrderItem.sku_id.is_(None), 1), else_=0)),
        )
        .where(SalesOrderItem.order_id.in_(order_ids))
        .group_by(SalesOrderItem.order_id)
    ).all()
    return {
        int(order_id): (int(item_count or 0), int(unbound_count or 0))
        for order_id, item_count, unbound_count in rows
    }


def build_order_briefs(db: Session, orders: list[SalesOrder]) -> list[dict]:
    """订单列表元素批量序列化（契约 19.4 列表）。"""
    if not orders:
        return []
    users, _ = _name_maps(db, orders)
    stats = _item_stats(db, [order.id for order in orders])
    briefs = []
    for order in orders:
        item_count, unbound_count = stats.get(order.id, (0, 0))
        briefs.append(
            order_brief(
                order,
                created_by_name=users.get(order.created_by),
                claimed_by_name=users.get(order.claimed_by),
                item_count=item_count,
                unbound_count=unbound_count,
            )
        )
    return briefs


def build_order_detail(db: Session, order: SalesOrder) -> dict:
    """订单详情序列化（契约 19.4 详情，含明细）。"""
    users, warehouses = _name_maps(db, [order])
    items = list(order.items)
    sku_ids = [item.sku_id for item in items if item.sku_id is not None]
    skus = (
        {s.id: s for s in db.scalars(select(ProductSku).where(ProductSku.id.in_(sku_ids)))}
        if sku_ids
        else {}
    )
    item_dicts = [order_item_out(item, skus.get(item.sku_id)) for item in items]
    return order_detail(
        order,
        created_by_name=users.get(order.created_by),
        claimed_by_name=users.get(order.claimed_by),
        warehouse_name=warehouses.get(order.warehouse_id),
        items=item_dicts,
    )


# ---------------------------------------------------------------- 库存预留


def build_order_outbound_changes(order: SalesOrder, warehouse_id: int) -> list[dict]:
    """按订单明细的剩余待出量构造库存变更明细（负数，出库方向）。

    四阶段的「接单预留 / 发货释放 / 取消释放」三处共用同一个构造方式，
    保证预留的量与释放的量永远一致。数量为 0 的明细直接跳过。

    六阶段起 `sku_id` 可空（尚未关联货号），这类行没有 SKU 可预留 / 释放，直接跳过；
    契约第十八节要求「全部关联完成才允许进入备货」，因此真正出库时不会再有空行。
    """
    changes: list[dict] = []
    for item in order.items:
        if item.sku_id is None:
            continue
        count = Decimal(item.count or 0) - Decimal(item.out_count or 0)
        if count > 0:
            changes.append(
                {"sku_id": item.sku_id, "warehouse_id": warehouse_id, "quantity": -count}
            )
    return changes


# ---------------------------------------------------------------- 接口


@router.post("", summary="创建订单")
def create_order(
    payload: SalesOrderCreateIn,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(require_roles("operator", "admin")),
):
    """运营录入外部平台订单（契约 19.1）。

    `no` 为运营录入的订单号，全局唯一；明细只记商品名 / 货号 / 新品标记，
    `sku_id` 留空由仓储端后续「关联货号」回填；status 固定 10，总额由后端汇总。
    """
    # 先做一次友好校验；并发下两个请求可能同时通过这里，靠 no 的唯一索引兜底
    if db.scalar(select(SalesOrder.id).where(SalesOrder.no == payload.no)) is not None:
        raise BizException(f"订单号已存在：{payload.no}")

    # 后端汇总总额，不信任前端传值
    total_count = sum((item.count for item in payload.items), Decimal("0"))
    total_price = sum(
        (
            (item.count * item.expect_price).quantize(CENT, rounding=ROUND_HALF_UP)
            for item in payload.items
        ),
        Decimal("0"),
    )

    order = SalesOrder(
        no=payload.no,
        status=ORDER_STATUS_PENDING,
        remark=payload.remark,
        total_count=total_count,
        total_price=total_price,
        created_by=current_user.id,
    )
    db.add(order)
    try:
        db.flush()
        for item in payload.items:
            db.add(
                SalesOrderItem(
                    order_id=order.id,
                    product_name=item.product_name,
                    sku_code=item.sku_code,
                    is_new=item.is_new,
                    sku_id=None,  # 尚未关联货号，由仓储端 bind-sku 回填
                    count=item.count,
                    out_count=Decimal("0"),
                    expect_price=item.expect_price,
                    total_price=(item.count * item.expect_price).quantize(
                        CENT, rounding=ROUND_HALF_UP
                    ),
                )
            )
        db.commit()
    except IntegrityError:
        # 唯一索引兜底：并发下另一个请求刚插入了同一个订单号
        db.rollback()
        raise BizException(f"订单号已存在：{payload.no}") from None

    db.refresh(order)
    return ok(build_order_detail(db, order), msg="下单成功")


@router.get("", summary="订单列表")
def list_orders(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1),
    status: int | None = Query(None, description="订单状态"),
    keyword: str | None = Query(None, description="单号 / 物流单号"),
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(require_roles("operator", "warehouse", "admin")),
):
    """订单列表（契约 19.4）。

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

    stmt = select(SalesOrder)
    count_stmt = select(func.count()).select_from(SalesOrder)
    if kw:
        pattern = f"%{kw}%"
        condition = or_(
            SalesOrder.no.like(pattern),
            SalesOrder.express_no.like(pattern),
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
    """取消订单。仅 status 在 10 / 20 / 25 / 30 时可取消；operator 只能取消自己的订单。

    运营确认数量只记录最终数量，不预留库存；库存采购与实际出库由仓储处理。
    因此取消订单不需要调整任何库存，只修改订单状态和取消原因。

    并发保护：先对订单行加 `FOR UPDATE` 锁，再读状态校验，避免并发下重复取消。
    """
    # 加行锁读取：保证「读状态 → 校验 → 改状态」之间没有其他事务插入
    order = get_order_or_404(db, order_id, for_update=True)
    ensure_visible(order, current_user)

    target = ensure_transition(order.status, "取消")

    order.status = target
    order.cancel_reason = payload.cancel_reason
    db.commit()
    db.refresh(order)
    return ok(build_order_detail(db, order), msg="订单已取消")


@router.post("/{order_id}/confirm-quantity", summary="确认数量（开始备货）")
def confirm_quantity(
    order_id: int,
    payload: ConfirmQuantityIn,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(require_roles("operator", "admin")),
):
    """运营确认数量：25「数量待确认」→ 30「备货中」（契约 19.6）。

    - 仅 `operator`（且只能操作自己创建的订单）/ `admin` 可调用；
    - 运营提交每个订单明细的最终数量，必须完整覆盖订单明细且不允许重复；
    - 处理顺序（同一事务）：校验状态 → 校验数量明细 → 更新数量汇总
      → 改状态 + 写 prepare_at；不校验或预留库存。

    并发保护：先对订单行加 `FOR UPDATE` 锁再读状态，避免同一订单被重复确认、
    重复写入数量。
    """
    # 加行锁读取：保证「读状态 → 校验数量 → 改状态」之间没有其他事务插入
    order = get_order_or_404(db, order_id, for_update=True)
    ensure_visible(order, current_user)

    # 非 25 时由 ensure_transition 抛 code=1001，msg 带当前状态中文名
    target = ensure_transition(order.status, "确认数量")

    # 请求必须恰好覆盖这张订单的全部明细，避免遗漏行沿用旧数量或跨订单篡改。
    order_items = {item.id: item for item in order.items}
    submitted_counts = {item.item_id: Decimal(item.count) for item in payload.items}
    if set(submitted_counts) != set(order_items):
        raise BizException("确认数量必须包含订单全部明细，且不能包含其他订单明细")

    total_count = Decimal("0.00")
    total_price = Decimal("0.00")
    for item in order.items:
        count = submitted_counts[item.id]
        item.count = count
        item.total_price = (count * Decimal(item.expect_price or 0)).quantize(
            CENT, rounding=ROUND_HALF_UP
        )
        total_count += count
        total_price += item.total_price

    order.total_count = total_count.quantize(CENT, rounding=ROUND_HALF_UP)
    order.total_price = total_price.quantize(CENT, rounding=ROUND_HALF_UP)
    order.status = target
    order.prepare_at = datetime.now()

    db.commit()
    db.refresh(order)
    return ok(build_order_detail(db, order), msg="已确认数量，开始备货")


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
