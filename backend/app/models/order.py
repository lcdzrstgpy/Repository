"""销售订单模型（契约 4.6 / 4.7）与状态定义（契约 3.2、第六节）。"""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, DateTime, ForeignKey, Numeric, String
from sqlalchemy.dialects.mysql import TINYINT
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, TimestampMixin

# 订单状态值（契约 3.2）
ORDER_STATUS_PENDING = 10  # 待接单
ORDER_STATUS_CLAIMED = 20  # 已接单
ORDER_STATUS_PREPARING = 30  # 备货中
ORDER_STATUS_SHIPPED = 40  # 已发货
ORDER_STATUS_FINISHED = 50  # 已完成
ORDER_STATUS_CANCELLED = 90  # 已取消

# 状态中文名，列表/详情接口的 status_text 与流转错误提示都取自这里
ORDER_STATUS_TEXT: dict[int, str] = {
    ORDER_STATUS_PENDING: "待接单",
    ORDER_STATUS_CLAIMED: "已接单",
    ORDER_STATUS_PREPARING: "备货中",
    ORDER_STATUS_SHIPPED: "已发货",
    ORDER_STATUS_FINISHED: "已完成",
    ORDER_STATUS_CANCELLED: "已取消",
}

# 审批状态（契约 3.3）
AUDIT_STATUS_UNAUDITED = 0  # 未审批
AUDIT_STATUS_AUDITED = 1  # 已审批

# 状态流转合法表（契约第六节）
# 键：操作名；值：(允许的当前状态集合, 目标状态)
ORDER_TRANSITIONS: dict[str, tuple[set[int], int]] = {
    "接单": ({ORDER_STATUS_PENDING}, ORDER_STATUS_CLAIMED),
    "备货": ({ORDER_STATUS_CLAIMED}, ORDER_STATUS_PREPARING),
    "发货": ({ORDER_STATUS_PREPARING}, ORDER_STATUS_SHIPPED),
    "确认完成": ({ORDER_STATUS_SHIPPED}, ORDER_STATUS_FINISHED),
    "取消": (
        {ORDER_STATUS_PENDING, ORDER_STATUS_CLAIMED, ORDER_STATUS_PREPARING},
        ORDER_STATUS_CANCELLED,
    ),
}


def status_text(status: int | None) -> str:
    """状态值转中文名，未知状态返回「未知状态」。"""
    if status is None:
        return "未知状态"
    return ORDER_STATUS_TEXT.get(int(status), "未知状态")


def ensure_transition(current_status: int | None, action: str) -> int:
    """校验状态流转是否合法，合法则返回目标状态。

    不合法时抛 BizException(code=1001)，msg 带上当前状态中文名，例如：
        「订单当前状态为「已接单」，无法执行接单操作」
    """
    # 延迟导入，避免 models 与 core.response 在包初始化阶段的相互依赖
    from app.core.response import BizException

    allowed, target = ORDER_TRANSITIONS[action]
    if current_status is None or int(current_status) not in allowed:
        raise BizException(
            f"订单当前状态为「{status_text(current_status)}」，无法执行{action}操作"
        )
    return target


class SalesOrder(Base, TimestampMixin):
    """销售订单主表。"""

    __tablename__ = "sales_order"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    no: Mapped[str] = mapped_column(
        String(32), unique=True, nullable=False, comment="单号 SO+yyyyMMdd+4位流水"
    )
    customer_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("partner.id"), nullable=False, comment="客户 partner.id"
    )
    status: Mapped[int] = mapped_column(
        TINYINT, nullable=False, default=ORDER_STATUS_PENDING, comment="见契约 3.2"
    )
    audit_status: Mapped[int] = mapped_column(
        TINYINT, nullable=False, default=AUDIT_STATUS_UNAUDITED, comment="0 未审批 / 1 已审批"
    )
    warehouse_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("warehouse.id"), nullable=True, comment="指派仓库，接单时写入"
    )
    claimed_by: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("sys_user.id"), nullable=True, comment="接单人 user_id"
    )
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, comment="接单时间")
    prepare_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, comment="开始备货时间")
    shipped_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, comment="发货时间")
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, comment="完成时间")
    express_no: Mapped[str | None] = mapped_column(String(64), nullable=True, comment="物流单号")
    cancel_reason: Mapped[str | None] = mapped_column(String(255), nullable=True, comment="取消原因")
    remark: Mapped[str | None] = mapped_column(String(500), nullable=True, comment="备注")
    total_count: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), nullable=False, default=Decimal("0.00"), comment="总数量（明细汇总）"
    )
    total_price: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), nullable=False, default=Decimal("0.00"), comment="总金额（明细汇总）"
    )
    created_by: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("sys_user.id"), nullable=False, comment="下单人 user_id"
    )

    items: Mapped[list["SalesOrderItem"]] = relationship(
        back_populates="order", cascade="all, delete-orphan", lazy="selectin"
    )


class SalesOrderItem(Base, TimestampMixin):
    """销售订单明细。"""

    __tablename__ = "sales_order_item"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    order_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("sales_order.id"), nullable=False, comment="关联 sales_order"
    )
    sku_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("product_sku.id"), nullable=False, comment="关联 product_sku"
    )
    count: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), nullable=False, default=Decimal("0.00"), comment="下单数量"
    )
    out_count: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), nullable=False, default=Decimal("0.00"), comment="已出库数量"
    )
    price: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), nullable=False, default=Decimal("0.00"), comment="单价"
    )
    total_price: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), nullable=False, default=Decimal("0.00"), comment="小计 = count × price"
    )

    order: Mapped["SalesOrder"] = relationship(back_populates="items")
