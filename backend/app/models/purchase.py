"""采购模型（契约 10.2）：采购单 / 采购明细 / 采购入库单 / 入库明细。

关键设计（契约 10.1）：采购单本身**不影响库存**，只有「收货入库」才通过
`change_inventory` 增加库存。订单类操作与库存类操作严格分离。
"""

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import BigInteger, Date, DateTime, ForeignKey, Numeric, String
from sqlalchemy.dialects.mysql import TINYINT
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, TimestampMixin

# 采购单状态值（契约 10.2）
PURCHASE_STATUS_PENDING = 10  # 待审批
PURCHASE_STATUS_APPROVED = 20  # 已审批
PURCHASE_STATUS_RECEIVED = 30  # 已入库
PURCHASE_STATUS_CANCELLED = 90  # 已取消

# 状态中文名，列表/详情接口的 status_text 与流转错误提示都取自这里
PURCHASE_STATUS_TEXT: dict[int, str] = {
    PURCHASE_STATUS_PENDING: "待审批",
    PURCHASE_STATUS_APPROVED: "已审批",
    PURCHASE_STATUS_RECEIVED: "已入库",
    PURCHASE_STATUS_CANCELLED: "已取消",
}

# 采购入库单状态值（契约 10.2：简化为创建即入库，只有「已完成」一态）
PURCHASE_IN_STATUS_DONE = 20  # 已完成

PURCHASE_IN_STATUS_TEXT: dict[int, str] = {
    PURCHASE_IN_STATUS_DONE: "已完成",
}


def purchase_status_text(status: int | None) -> str:
    """采购单状态值转中文名，未知状态返回「未知状态」。"""
    if status is None:
        return "未知状态"
    return PURCHASE_STATUS_TEXT.get(int(status), "未知状态")


def purchase_in_status_text(status: int | None) -> str:
    """采购入库单状态值转中文名，未知状态返回「未知状态」。"""
    if status is None:
        return "未知状态"
    return PURCHASE_IN_STATUS_TEXT.get(int(status), "未知状态")


class PurchaseOrder(Base, TimestampMixin):
    """采购单主表（契约 10.2）。"""

    __tablename__ = "purchase_order"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    no: Mapped[str] = mapped_column(
        String(32), unique=True, nullable=False, comment="单号 PO+yyyyMMdd+4位流水"
    )
    supplier_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("partner.id"), nullable=False, index=True, comment="供应商 partner.id（type 含 2）"
    )
    sales_order_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("sales_order.id"),
        nullable=True,
        index=True,
        comment="关联销售订单 id（因缺货采购时写入）",
    )
    status: Mapped[int] = mapped_column(
        TINYINT,
        nullable=False,
        default=PURCHASE_STATUS_PENDING,
        index=True,
        comment="10 待审批 / 20 已审批 / 30 已入库 / 90 已取消",
    )
    total_count: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), nullable=False, default=Decimal("0.00"), comment="总数量（明细汇总）"
    )
    total_price: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), nullable=False, default=Decimal("0.00"), comment="总金额（明细汇总）"
    )
    expect_date: Mapped[date | None] = mapped_column(Date, nullable=True, comment="期望到货日期")
    remark: Mapped[str | None] = mapped_column(String(500), nullable=True, comment="备注")
    created_by: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("sys_user.id"), nullable=False, index=True, comment="创建人 user_id"
    )
    approved_by: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("sys_user.id"), nullable=True, comment="审批人 user_id"
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, comment="审批时间")

    items: Mapped[list["PurchaseOrderItem"]] = relationship(
        back_populates="order", cascade="all, delete-orphan", lazy="selectin"
    )


class PurchaseOrderItem(Base, TimestampMixin):
    """采购明细（契约 10.2）。in_count 支持部分入库，累加不超过 count。"""

    __tablename__ = "purchase_order_item"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    order_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("purchase_order.id"),
        nullable=False,
        index=True,
        comment="关联 purchase_order",
    )
    sku_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("product_sku.id"), nullable=False, index=True, comment="SKU id"
    )
    count: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), nullable=False, default=Decimal("0.00"), comment="采购数量"
    )
    in_count: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), nullable=False, default=Decimal("0.00"), comment="已入库数量"
    )
    price: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), nullable=False, default=Decimal("0.00"), comment="单价"
    )
    total_price: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), nullable=False, default=Decimal("0.00"), comment="小计 = count × price"
    )

    order: Mapped["PurchaseOrder"] = relationship(back_populates="items")


class PurchaseIn(Base, TimestampMixin):
    """采购入库单（契约 10.2）。收货入库时生成，创建即完成。"""

    __tablename__ = "purchase_in"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    no: Mapped[str] = mapped_column(
        String(32), unique=True, nullable=False, comment="单号 IN+yyyyMMdd+4位流水"
    )
    order_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("purchase_order.id"),
        nullable=False,
        index=True,
        comment="关联 purchase_order",
    )
    order_no: Mapped[str] = mapped_column(String(32), nullable=False, comment="冗余采购单号")
    warehouse_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("warehouse.id"), nullable=False, index=True, comment="入库仓库 id"
    )
    status: Mapped[int] = mapped_column(
        TINYINT,
        nullable=False,
        default=PURCHASE_IN_STATUS_DONE,
        comment="20 已完成（简化为创建即入库）",
    )
    total_count: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), nullable=False, default=Decimal("0.00"), comment="总数量"
    )
    total_price: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), nullable=False, default=Decimal("0.00"), comment="总金额"
    )
    remark: Mapped[str | None] = mapped_column(String(500), nullable=True, comment="备注")
    created_by: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("sys_user.id"), nullable=False, comment="创建人 user_id"
    )

    items: Mapped[list["PurchaseInItem"]] = relationship(
        back_populates="purchase_in", cascade="all, delete-orphan", lazy="selectin"
    )


class PurchaseInItem(Base, TimestampMixin):
    """入库明细（契约 10.2）。"""

    __tablename__ = "purchase_in_item"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    in_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("purchase_in.id"), nullable=False, index=True, comment="关联 purchase_in"
    )
    order_item_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("purchase_order_item.id"),
        nullable=False,
        index=True,
        comment="关联 purchase_order_item",
    )
    sku_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("product_sku.id"), nullable=False, index=True, comment="SKU id"
    )
    count: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), nullable=False, default=Decimal("0.00"), comment="本次入库数量"
    )
    price: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), nullable=False, default=Decimal("0.00"), comment="单价"
    )
    total_price: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), nullable=False, default=Decimal("0.00"), comment="小计"
    )

    purchase_in: Mapped["PurchaseIn"] = relationship(back_populates="items")
