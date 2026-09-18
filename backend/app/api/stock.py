"""出库单接口（契约 9.4）。

出库单由「发货」动作自动生成，仓储端在这里查询与作废；
发货本身仍走 `POST /api/warehouse/orders/{id}/ship`。
"""

from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.order import build_order_outbound_changes
from app.core.database import get_db
from app.core.response import BizException, NotFoundException, normalize_page, ok, paginate
from app.core.security import require_roles
from app.models.basic import Product, ProductSku, Warehouse
from app.models.order import (
    ORDER_STATUS_FINISHED,
    ORDER_STATUS_PREPARING,
    SalesOrder,
    SalesOrderItem,
    status_text,
)
from app.models.stock import (
    SALES_OUT_STATUS_CANCELLED,
    SALES_OUT_STATUS_DONE,
    SalesOut,
    SalesOutItem,
)
from app.models.user import SysUser
from app.schemas.stock import sales_out_brief, sales_out_detail, sales_out_item_out
from app.services.inventory_service import (
    ORDER_TYPE_SALES_OUT,
    change_inventory,
    reserve_inventory,
)

router = APIRouter(prefix="/api/sales-outs", tags=["仓储侧·出库单"])

# 金额统一保留 2 位小数，四舍五入
CENT = Decimal("0.01")


# ---------------------------------------------------------------- 通用工具
def get_sales_out_or_404(db: Session, out_id: int) -> SalesOut:
    """按 id 取出库单，不存在抛 404。"""
    out = db.get(SalesOut, out_id)
    if out is None:
        raise NotFoundException("出库单不存在")
    return out


def generate_sales_out_no(db: Session, offset: int = 0) -> str:
    """生成单号：OUT + yyyyMMdd + 4 位当日流水，如 OUT202609160001。"""
    prefix = "OUT" + datetime.now().strftime("%Y%m%d")
    max_no = db.scalar(select(func.max(SalesOut.no)).where(SalesOut.no.like(f"{prefix}%")))
    seq = 1
    if max_no:
        try:
            seq = int(str(max_no)[-4:]) + 1
        except ValueError:
            seq = 1
    return f"{prefix}{seq + offset:04d}"


def _load_names(db: Session, outs: list[SalesOut]) -> tuple[dict, dict]:
    """批量取仓库名、操作人姓名，避免逐行查询。

    六阶段（契约 17.1 / 19.4）订单已删除客户字段，出库单也不再展示客户名，
    因此这里只返回仓库名与操作人姓名，分别按 warehouse_id / user_id 索引。
    """
    warehouse_ids = {out.warehouse_id for out in outs if out.warehouse_id}
    user_ids = {out.created_by for out in outs if out.created_by}
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


def build_sales_out_briefs(db: Session, outs: list[SalesOut]) -> list[dict]:
    """出库单列表元素批量序列化。"""
    if not outs:
        return []
    warehouses, users = _load_names(db, outs)
    return [
        sales_out_brief(
            out,
            warehouse_name=warehouses.get(out.warehouse_id),
            created_by_name=users.get(out.created_by),
        )
        for out in outs
    ]


def build_sales_out_detail(db: Session, out: SalesOut) -> dict:
    """出库单详情序列化，含明细（带 sku_code / product_name / spec）。"""
    warehouses, users = _load_names(db, [out])
    items = list(
        db.scalars(
            select(SalesOutItem)
            .where(SalesOutItem.out_id == out.id)
            .order_by(SalesOutItem.id.asc())
        )
    )
    sku_ids = {item.sku_id for item in items}
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
        sales_out_item_out(
            item,
            skus.get(item.sku_id),
            products.get(skus[item.sku_id].product_id) if item.sku_id in skus else None,
        )
        for item in items
    ]
    return sales_out_detail(
        out,
        warehouse_name=warehouses.get(out.warehouse_id),
        created_by_name=users.get(out.created_by),
        items=item_dicts,
    )


# ---------------------------------------------------------------- 供发货接口复用
def create_sales_out_from_order(
    db: Session, order: SalesOrder, operator_id: int, express_no: str | None = None
) -> SalesOut:
    """发货时生成一张「已完成」的出库单，并扣减库存、回写明细 out_count。

    :param express_no: 本次发货的物流单号，写入出库单
    本函数不提交事务，由 ship 接口统一 commit，保证扣库存与改订单状态同事务。
    """
    if order.warehouse_id is None:
        raise BizException("订单未指派仓库，无法出库")

    items = list(order.items)
    if not items:
        raise BizException("订单没有明细，无法出库")

    # 出库数量取订单明细的剩余待出量：count - out_count
    lines: list[tuple[SalesOrderItem, Decimal]] = []
    for item in items:
        count = Decimal(item.count or 0) - Decimal(item.out_count or 0)
        if count > 0:
            lines.append((item, count.quantize(CENT, rounding=ROUND_HALF_UP)))
    if not lines:
        raise BizException("订单明细已全部出库，无需重复发货")

    total_count = sum((count for _, count in lines), Decimal("0.00"))
    # 六阶段（契约 17.2）：订单行单价由 `price` 重命名为 `expect_price`（预计成本单价）
    total_price = sum(
        (
            (count * Decimal(item.expect_price or 0)).quantize(CENT, rounding=ROUND_HALF_UP)
            for item, count in lines
        ),
        Decimal("0.00"),
    )

    # sales_out.no 有唯一索引：并发下可能撞号，用 savepoint 包住后重试
    out: SalesOut | None = None
    for attempt in range(5):
        candidate = SalesOut(
            no=generate_sales_out_no(db, offset=attempt),
            order_id=order.id,
            order_no=order.no,
            warehouse_id=order.warehouse_id,
            status=SALES_OUT_STATUS_DONE,
            total_count=total_count,
            total_price=total_price,
            express_no=express_no if express_no is not None else order.express_no,
            remark=order.remark,
            created_by=operator_id,
        )
        try:
            with db.begin_nested():
                db.add(candidate)
            out = candidate
            break
        except IntegrityError:
            continue
    if out is None:
        raise BizException("出库单号生成冲突，请稍后重试")

    # 扣库存（负数出库），库存不足会抛 code=1001
    change_inventory(
        db,
        [
            {"sku_id": item.sku_id, "warehouse_id": order.warehouse_id, "quantity": -count}
            for item, count in lines
        ],
        out.no,
        ORDER_TYPE_SALES_OUT,
        operator_id,
    )

    for item, count in lines:
        db.add(
            SalesOutItem(
                out_id=out.id,
                order_item_id=item.id,
                sku_id=item.sku_id,
                count=count,
                price=item.expect_price,
                total_price=(count * Decimal(item.expect_price or 0)).quantize(
                    CENT, rounding=ROUND_HALF_UP
                ),
            )
        )
        item.out_count = (Decimal(item.out_count or 0) + count).quantize(
            CENT, rounding=ROUND_HALF_UP
        )

    db.flush()
    return out


# ---------------------------------------------------------------- 接口
@router.get("", summary="出库单列表")
def list_sales_outs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1),
    keyword: str | None = Query(None, description="出库单号 / 订单号 / 物流单号"),
    warehouse_id: int | None = Query(None, description="按仓库筛选"),
    db: Session = Depends(get_db),
    _current_user: SysUser = Depends(require_roles("warehouse")),
):
    """出库单列表。"""
    page, page_size = normalize_page(page, page_size)

    conditions = []
    if warehouse_id is not None:
        conditions.append(SalesOut.warehouse_id == warehouse_id)
    kw = (keyword or "").strip()

    stmt = select(SalesOut)
    count_stmt = select(func.count()).select_from(SalesOut)
    if kw:
        pattern = f"%{kw}%"
        condition = or_(
            SalesOut.no.like(pattern),
            SalesOut.order_no.like(pattern),
            SalesOut.express_no.like(pattern),
        )
        stmt = stmt.where(condition)
        count_stmt = count_stmt.where(condition)
    if conditions:
        stmt = stmt.where(*conditions)
        count_stmt = count_stmt.where(*conditions)

    total = db.scalar(count_stmt) or 0
    rows = db.scalars(
        stmt.order_by(SalesOut.id.desc()).offset((page - 1) * page_size).limit(page_size)
    ).all()
    return ok(paginate(build_sales_out_briefs(db, list(rows)), total, page, page_size))


@router.get("/{out_id}", summary="出库单详情")
def get_sales_out(
    out_id: int,
    db: Session = Depends(get_db),
    _current_user: SysUser = Depends(require_roles("warehouse")),
):
    """出库单详情，含明细。"""
    out = get_sales_out_or_404(db, out_id)
    return ok(build_sales_out_detail(db, out))


@router.post("/{out_id}/cancel", summary="作废出库单")
def cancel_sales_out(
    out_id: int,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(require_roles("warehouse")),
):
    """作废出库单：反向回滚库存，关联订单从「已完成」退回「备货中」。

    四阶段（契约 12.2）：发货时预留已随「预留转实扣」释放，作废只回滚实扣的
    `quantity`。但订单退回「备货中(30)」后还要能再次发货，而「发货」会释放预留——
    因此这里必须**重新预留**，让订单回到「持有预留」的一致状态（P1-1，方案 A）。
    若此时可用量已被别的订单占用、重新预留失败，则整体报错阻止作废（同一事务回滚），
    避免订单在「不持有预留」的状态下再次发货、误扣其他订单的预留量。

    并发保护：先锁出库单行，再锁关联订单行，最后锁库存行，防止并发重复作废。
    """
    # 加行锁读取出库单，避免两个请求同时作废
    out = db.scalars(
        select(SalesOut).where(SalesOut.id == out_id).with_for_update()
    ).first()
    if out is None:
        raise NotFoundException("出库单不存在")
    if out.status == SALES_OUT_STATUS_CANCELLED:
        raise BizException("出库单已作废，无法重复作废")
    if out.status != SALES_OUT_STATUS_DONE:
        raise BizException("仅「已完成」的出库单可以作废")

    items = list(db.scalars(select(SalesOutItem).where(SalesOutItem.out_id == out.id)))
    # 加行锁读取关联订单，避免与发货 / 取消订单并发冲突
    order = (
        db.scalars(
            select(SalesOrder).where(SalesOrder.id == out.order_id).with_for_update()
        ).first()
        if out.order_id
        else None
    )

    # 先校验订单状态，避免回滚了库存才发现订单退不回去
    # 发货即完成，故正常情况订单为「已完成(50)」；改造前遗留的「已发货(40)」
    # 在存量数据刷成 50 之前同样放行。
    if order is not None and order.status not in (ORDER_STATUS_FINISHED, 40):
        raise BizException(
            f"订单当前状态为「{status_text(order.status)}」，无法作废出库单"
        )

    # 反向回滚库存（正数加回）
    # 四阶段（契约 12.2）：这里只回滚「实扣」的 quantity，**不要动 reserved_quantity**——
    # 预留早在发货那一刻就随「预留转实扣」释放掉了，再动一次会导致预留量被重复扣减。
    change_inventory(
        db,
        [
            {
                "sku_id": item.sku_id,
                "warehouse_id": out.warehouse_id,
                "quantity": Decimal(item.count or 0),
            }
            for item in items
        ],
        out.no,
        ORDER_TYPE_SALES_OUT,
        current_user.id,
    )

    # 关联订单退回「备货中」，同时撤销发货痕迹与已出库数量
    if order is not None:
        order.status = ORDER_STATUS_PREPARING
        order.shipped_at = None
        order.finished_at = None
        order.express_no = None
        for item in items:
            if not item.order_item_id:
                continue
            order_item = db.get(SalesOrderItem, item.order_item_id)
            if order_item is None:
                continue
            remain = Decimal(order_item.out_count or 0) - Decimal(item.count or 0)
            order_item.out_count = max(Decimal("0.00"), remain).quantize(
                CENT, rounding=ROUND_HALF_UP
            )

        # P1-1 方案 A：订单退回「备货中」后要重新持有预留。
        # 必须先回滚 out_count 再构造预留量，否则剩余待出量算出来是 0。
        # 预留与库存回滚在同一事务、同一批已加锁的行上，可用量不足会抛 code=1001 并整体回滚。
        reserve_inventory(
            db,
            build_order_outbound_changes(order, out.warehouse_id),
            order.no,
            current_user.id,
        )

    out.status = SALES_OUT_STATUS_CANCELLED
    db.commit()
    db.refresh(out)
    return ok(build_sales_out_detail(db, out), msg="出库单已作废")
