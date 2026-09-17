"""仓储侧订单处理接口（契约 5.4）：待接单、接单、关联货号、发货。

发货接口在二阶段增强为真实库存操作（契约 9.1）：扣库存 + 生成出库单。
四阶段（契约 12.2）增加库存预留；六阶段（契约 19.2 / 19.7）新增「关联货号」后，
订单明细的 `sku_id` 由仓储端回填，全部绑完即自动流转到「数量待确认(25)」；
运营确认最终数量后直接进入「备货中」；库存不足由仓储采购处理，只有真正发货时才校验
库存。原 `prepare` 接口（20 → 30）已废弃。
"""

import logging
from datetime import datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field, field_validator, model_validator
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
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
from app.models.basic import Product, ProductSku, Warehouse
from app.models.order import (
    ORDER_STATUS_CLAIMED,
    ORDER_STATUS_PENDING,
    ORDER_STATUS_QUANTITY_CONFIRM,
    SalesOrder,
    ensure_transition,
    status_text,
)
from app.models.user import SysUser
from app.schemas.order import ClaimIn, ShipIn
from app.services.inventory_service import check_available, shortage_message

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

    六阶段（契约 19.2 / 18.1）：新流程下接单时订单行尚未关联货号（`sku_id` 为空），
    无法确定要预留哪个 SKU，因此**接单不再预留库存**；预留改到**运营确认数量
    （25 → 30）**时进行（契约保证那时所有行都已绑定货号）。这里只做仓库可用性
    校验与状态流转。

    并发保护：先对订单行加 `FOR UPDATE` 锁再读状态，避免两个仓储用户同时接单。
    """
    # 加行锁读取：保证「读状态 → 校验 → 改状态」之间没有其他事务插入
    order = get_order_or_404(db, order_id, for_update=True)
    target = ensure_transition(order.status, "接单")

    warehouse = db.get(Warehouse, payload.warehouse_id)
    if warehouse is None:
        raise BizException("仓库不存在")
    if warehouse.status != 1:
        raise BizException(f"仓库「{warehouse.name}」已停用，无法接单")

    order.status = target
    order.warehouse_id = warehouse.id
    order.claimed_by = current_user.id
    order.claimed_at = datetime.now()
    db.commit()
    db.refresh(order)
    return ok(build_order_detail(db, order), msg="接单成功")


# ---------------------------------------------------------------- 关联货号（契约 19.2）


class NewSkuIn(BaseModel):
    """「新建」模式入参：仓库现场新建一个货号（SKU）。"""

    sku_code: str = Field(..., min_length=1, max_length=64, description="新货号")
    product_name: str = Field(..., min_length=1, max_length=200, description="商品名")
    spec: str | None = Field(None, max_length=200, description="规格")
    price: Decimal = Field(Decimal("0.00"), ge=0, description="售价")

    @field_validator("sku_code", "product_name", mode="before")
    @classmethod
    def strip_text(cls, value):
        """货号 / 商品名去掉首尾空白，避免「 HW-001 」与「HW-001」被当成两个货号。"""
        if isinstance(value, str):
            return value.strip()
        return value


class BindSkuItemIn(BaseModel):
    """单个订单行的关联请求：`sku_code`（关联已有）与 `new_sku`（新建）二选一。"""

    item_id: int = Field(..., gt=0, description="订单明细 id")
    sku_code: str | None = Field(None, max_length=64, description="关联已有货号")
    new_sku: NewSkuIn | None = Field(None, description="新建货号")

    @field_validator("sku_code", mode="before")
    @classmethod
    def normalize_sku_code(cls, value):
        """货号去空白；空串视为未填写（前端清空输入框时常传 ""）。"""
        if isinstance(value, str):
            value = value.strip()
            return value or None
        return value

    @model_validator(mode="after")
    def check_mode(self) -> "BindSkuItemIn":
        """契约 16.3 硬规则 1：每个订单行必须「填了货号」或「勾选新品」二选一。"""
        if bool(self.sku_code) == (self.new_sku is not None):
            raise ValueError("每行必须且只能选择「关联已有货号」或「新建货号」之一")
        return self


class BindSkuIn(BaseModel):
    """bind-sku 请求体（契约 19.2），支持一次只关联一部分行。"""

    items: list[BindSkuItemIn] = Field(..., min_length=1, description="待关联的订单明细，至少一条")


def _generate_product_code(db: Session) -> str:
    """为新商品生成编码，沿用既有「P + 3 位流水」格式（P001 / P002 ...）。

    取当前最大的 P 开头编码递增；若与手工录入的编码冲突则继续向后找空位。
    """
    max_code = db.scalar(select(func.max(Product.code)).where(Product.code.like("P%")))
    seq = 1
    if max_code:
        try:
            seq = int(str(max_code)[1:]) + 1
        except ValueError:
            seq = 1
    while db.scalar(select(Product.id).where(Product.code == f"P{seq:03d}")) is not None:
        seq += 1
    return f"P{seq:03d}"


def _create_sku_for_item(db: Session, new_sku: NewSkuIn) -> int:
    """「新建」模式：按货号创建 SKU（同名商品已存在则复用），返回新 SKU 的 id。

    商品按 `product_name` 查找，不存在才创建（编码自动生成）；
    `sku_code` 重复时返回 code=1001。函数内不 commit，由调用方统一提交。
    """
    if db.scalar(select(ProductSku.id).where(ProductSku.sku_code == new_sku.sku_code)) is not None:
        raise BizException(f"货号 {new_sku.sku_code} 已存在，请改为关联已有货号")

    product = db.scalar(select(Product).where(Product.name == new_sku.product_name))
    if product is None:
        product = Product(
            code=_generate_product_code(db),
            name=new_sku.product_name,
            status=1,
        )
        db.add(product)
        db.flush()  # 会话 autoflush=False，需显式 flush 才能拿到 product.id

    sku = ProductSku(
        product_id=product.id,
        sku_code=new_sku.sku_code,
        spec=new_sku.spec,
        price=new_sku.price,
        min_stock=Decimal("0.00"),
        status=1,
    )
    db.add(sku)
    db.flush()  # 拿到 sku.id，同时让同一请求内重复的货号能被查出来
    return sku.id


@router.post("/orders/{order_id}/bind-sku", summary="关联 / 新建货号")
def bind_order_sku(
    order_id: int,
    payload: BindSkuIn,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(require_roles("warehouse", "admin")),
):
    """为订单明细行关联已有货号或新建货号（契约 19.2 / 19.7）。

    - 仅「已接单(20)」的订单可操作，支持部分关联，可多次调用直到全部完成；
    - 已关联（`sku_id` 非空）的行锁定，不允许再次修改（契约 16.3 硬规则 2）；
    - 全部关联完成后，订单自动流转到「数量待确认(25)」，等运营确认数量；
      部分关联时状态保持 20。
    - 整个请求（关联回填 + 自动流转）在一个事务里提交：任一行失败则全部回滚。
    """
    # 加行锁：与其它 bind-sku 并发时串行化，避免同一行被重复关联
    order = get_order_or_404(db, order_id, for_update=True)
    if order.status != ORDER_STATUS_CLAIMED:
        raise BizException(
            f"订单当前状态为「{status_text(order.status)}」，只有「已接单」的订单可以关联货号"
        )

    items = {item.id: item for item in order.items}
    try:
        for line in payload.items:
            item = items.get(line.item_id)
            if item is None:
                raise BizException(f"明细(id={line.item_id})不属于该订单，无法关联")
            if item.sku_id is not None:
                # 契约 16.3 硬规则 2：关联后锁定，运营与仓储均不可再改
                raise BizException("该商品已关联货号，不可修改")

            if line.sku_code:
                # 模式一：关联已有货号，按货号查找系统里的 SKU 后回填 sku_id
                sku = db.scalar(select(ProductSku).where(ProductSku.sku_code == line.sku_code))
                if sku is None:
                    raise BizException(f"货号 {line.sku_code} 在系统中不存在，请改为新建")
                item.sku_id = sku.id
            else:
                # 模式二：新建货号（new_sku 已在 Pydantic 层保证非空）
                item.sku_id = _create_sku_for_item(db, line.new_sku)

        # 契约 19.7：本次调用完成后若所有明细行的 sku_id 均不为空，则自动从「已接单(20)」
        # 流转到「数量待确认(25)」。部分关联时 all() 为 False，状态保持 20。
        # 订单至少有一行明细（契约 19.1），这里仍兜一层空集合，避免空订单被误流转。
        if order.items and all(item.sku_id is not None for item in order.items):
            order.status = ORDER_STATUS_QUANTITY_CONFIRM

        db.commit()
    except BizException:
        # 中途某行失败：整批回滚，避免出现「关联了一半」的中间态
        db.rollback()
        raise
    except IntegrityError:
        # 唯一索引兜底：并发下同一货号 / 商品编码被同时创建
        db.rollback()
        raise BizException("货号已存在，请刷新后重试") from None

    db.refresh(order)
    return ok(build_order_detail(db, order), msg="货号关联成功")


@router.post("/orders/{order_id}/prepare", summary="开始备货（已废弃）")
def prepare_order(
    order_id: int,
    _current_user: SysUser = Depends(require_roles("warehouse", "admin")),
):
    """已废弃（契约第十八节）：保留路由避免前端旧代码直接 404。

    状态流转改由运营的 `confirm-quantity`（25 → 30）统一负责，
    这里不再做任何状态校验、流转或库存操作，统一返回 code=1001 提示流程已变更。
    """
    raise BizException("流程已变更，备货由运营确认数量后自动开始")


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

    这是状态回传点：运营端轮询列表即可看到状态变为「已发货」。

    并发保护：先对订单行加 `FOR UPDATE` 锁再读状态，避免并发下重复发货、重复扣库存。
    """
    # 加行锁读取：保证「读状态 → 扣库存 → 改状态」之间没有其他事务插入
    order = get_order_or_404(db, order_id, for_update=True)
    target = ensure_transition(order.status, "发货")

    if order.warehouse_id is None:
        raise BizException("订单未指派仓库，无法发货")

    changes = build_order_outbound_changes(order, order.warehouse_id)

    # 契约第十八节：未关联货号的行在 prepare 已拦住，这里再兜一层——
    # 这类行没有 SKU 可出，build_order_outbound_changes 会跳过它们，发货不会因此崩溃。
    unbound_item_ids = [item.id for item in order.items if item.sku_id is None]
    if unbound_item_ids:
        logger.warning(
            "发货时订单仍有未关联货号的明细，已跳过这些行：order_no=%s, 明细=%s",
            order.no,
            unbound_item_ids,
        )

    # 发货前预校验库存，不足时给出「哪个 SKU 缺多少」的友好提示
    shortages = check_available(db, changes)
    if shortages:
        raise BizException("库存不足，" + shortage_message(shortages))

    # 扣库存 + 生成出库单 + 回写明细 out_count（同一事务）
    # 注意：出库单号可能撞号重试，重试用 savepoint 回滚，
    # 所以订单字段的修改放在这一步之后，避免被 savepoint 回滚波及。
    create_sales_out_from_order(db, order, current_user.id, payload.express_no)

    order.status = target
    order.shipped_at = datetime.now()
    order.express_no = payload.express_no
    db.commit()
    db.refresh(order)
    return ok(build_order_detail(db, order), msg="发货成功")
