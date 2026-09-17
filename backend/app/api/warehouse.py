"""仓储侧订单处理接口（契约 5.4）：待接单、接单、备货、发货。

发货接口在二阶段增强为真实库存操作（契约 9.1）：扣库存 + 生成出库单。
四阶段（契约 12.2）增加库存预留：接单时预留，发货时「预留转实扣」。
"""

import logging
from datetime import datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.order import (
    build_order_briefs,
    build_order_detail,
    build_order_outbound_changes,
    get_order_or_404,
)
from app.api.stock import create_sales_out_from_order
from app.core.database import get_db
from app.core.response import BizException, normalize_page, ok, paginate
from app.core.security import require_roles
from app.models.basic import Warehouse
from app.models.order import ORDER_STATUS_PARTIALLY_SHIPPED, ORDER_STATUS_PENDING, ORDER_STATUS_SHIPPED, SalesOrder, ensure_transition
from app.models.user import SysUser
from app.schemas.order import ClaimIn, ShipIn
from app.services.inventory_service import (
    check_available,
    release_inventory,
    reserve_inventory,
    shortage_message,
)

router = APIRouter(prefix="/api/warehouse", tags=["仓储侧·订单处理"])

logger = logging.getLogger(__name__)


@router.get("/pending-orders", summary="待接单列表")
def pending_orders(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1),
    db: Session = Depends(get_db),
    _current_user: SysUser = Depends(require_roles("warehouse", "admin")),
):
    """订单池：返回 status = 10 的全部订单（不分下单人）。"""
    page, page_size = normalize_page(page, page_size)
    condition = SalesOrder.status == ORDER_STATUS_PENDING
    total = db.scalar(select(func.count()).select_from(SalesOrder).where(condition)) or 0
    rows = db.scalars(
        select(SalesOrder)
        .where(condition)
        .order_by(SalesOrder.id.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return ok(paginate(build_order_briefs(db, list(rows)), total, page, page_size))


@router.post("/orders/{order_id}/claim", summary="接单")
def claim_order(
    order_id: int,
    payload: ClaimIn,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(require_roles("warehouse", "admin")),
):
    """接单。仅 status = 10 可接单，写 claimed_by / claimed_at / warehouse_id。

    四阶段（契约 12.2）：接单即预留库存——把货「锁」给这张订单，
    避免多张待发货订单同时看到同一批货，到发货时才发现不够。
    预留量与状态变更在同一事务里提交。

    并发保护：先对订单行加 `FOR UPDATE` 锁再读状态，避免两个仓储用户同时接单；
    预留的可用量校验在库存行加锁之后进行（P1-2），双重保证不超卖。
    """
    # 加行锁读取：保证「读状态 → 校验 → 预留 → 改状态」之间没有其他事务插入
    order = get_order_or_404(db, order_id, for_update=True)
    target = ensure_transition(order.status, "接单")

    warehouse = db.get(Warehouse, payload.warehouse_id)
    if warehouse is None:
        raise BizException("仓库不存在")
    if warehouse.status != 1:
        raise BizException(f"仓库「{warehouse.name}」已停用，无法接单")

    # 预留前先校验可用量（quantity - reserved_quantity），不足直接返回 code=1001
    changes = build_order_outbound_changes(order, warehouse.id)
    shortages = check_available(db, changes)
    if shortages:
        raise BizException("库存不足，" + shortage_message(shortages))

    # 只增加 reserved_quantity，不改 quantity，不写库存流水
    reserve_inventory(db, changes, order.no, current_user.id)

    order.status = target
    order.warehouse_id = warehouse.id
    order.claimed_by = current_user.id
    order.claimed_at = datetime.now()
    db.commit()
    db.refresh(order)
    return ok(build_order_detail(db, order), msg="接单成功")


@router.post("/orders/{order_id}/prepare", summary="开始备货")
def prepare_order(
    order_id: int,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(require_roles("warehouse", "admin")),
):
    """开始备货。仅 status = 20 可备货，写 prepare_at。"""
    order = get_order_or_404(db, order_id)
    target = ensure_transition(order.status, "备货")
    order.status = target
    order.prepare_at = datetime.now()
    db.commit()
    db.refresh(order)
    return ok(build_order_detail(db, order), msg="已开始备货")


@router.post("/orders/{order_id}/ship", summary="发货")
def ship_order(
    order_id: int,
    payload: ShipIn,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(require_roles("warehouse", "admin")),
):
    """发货。仅 status = 30 可发货，写 shipped_at / express_no。

    二阶段增强（契约 9.1）：发货会真实扣减库存并生成一张已完成状态的出库单，
    请求/响应格式保持不变。

    四阶段增强（契约 12.2）：发货 = 预留转实扣——先释放接单时占用的预留量，
    再走原有的实扣逻辑；释放与实扣在同一事务里，失败一起回滚。

    这是状态回传点：运营端轮询列表即可看到状态变为「已发货」。

    并发保护：先对订单行加 `FOR UPDATE` 锁再读状态，避免并发下重复发货、
    重复释放预留、重复扣库存。
    """
    # 加行锁读取：保证「读状态 → 释放预留 → 扣库存 → 改状态」之间没有其他事务插入
    order = get_order_or_404(db, order_id, for_update=True)
    ensure_transition(order.status, "发货")

    if order.warehouse_id is None:
        raise BizException("订单未指派仓库，无法发货")

    item = order.items[0] if order.items else None
    if item is None:
        raise BizException("订单没有货号明细，无法发货")
    remain = Decimal(item.count or 0) - Decimal(item.out_count or 0)
    if payload.count > remain:
        raise BizException(f"本次发货数量不能超过剩余待发数量 {remain}")
    changes = [{"sku_id": item.sku_id, "warehouse_id": order.warehouse_id, "quantity": -payload.count}]

    # 先释放预留，再做可用量预校验：
    # 若不先释放，本单自己占用的预留量会把可用量算少，导致误报库存不足。
    warnings = release_inventory(db, changes, order.no, current_user.id)
    if warnings:
        # 预留账实不符：释放量超过当前预留量，已钳制为 0（P2-2）。
        logger.warning(
            "发货时释放预留出现账实不符，已钳制为 0：order_no=%s, 明细=%s",
            order.no,
            warnings,
        )

    # 发货前预校验库存，不足时给出「哪个 SKU 缺多少」的友好提示
    shortages = check_available(db, changes)
    if shortages:
        raise BizException("库存不足，" + shortage_message(shortages))

    # 扣库存 + 生成出库单 + 回写明细 out_count（同一事务）
    # 注意：出库单号可能撞号重试，重试用 savepoint 回滚，
    # 所以订单字段的修改放在这一步之后，避免被 savepoint 回滚波及。
    create_sales_out_from_order(db, order, current_user.id, payload.express_no, payload.count)

    order.status = ORDER_STATUS_SHIPPED if payload.count == remain else ORDER_STATUS_PARTIALLY_SHIPPED
    order.shipped_at = datetime.now()
    order.express_no = payload.express_no
    db.commit()
    db.refresh(order)
    return ok(build_order_detail(db, order), msg="发货成功")
