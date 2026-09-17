"""出库单模型（契约 9.2）。发货时自动生成，作为发货凭证。"""

from decimal import Decimal

from sqlalchemy import BigInteger, ForeignKey, Numeric, String
from sqlalchemy.dialects.mysql import TINYINT
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, TimestampMixin

# 出库单状态值（契约 9.2）
SALES_OUT_STATUS_DRAFT = 10  # 草稿
SALES_OUT_STATUS_DONE = 20  # 已完成
SALES_OUT_STATUS_CANCELLED = 90  # 已作废

# 状态中文名，列表/详情接口的 status_text 与流转错误提示都取自这里
SALES_OUT_STATUS_TEXT: dict[int, str] = {
    SALES_OUT_STATUS_DRAFT: "草稿",
    SALES_OUT_STATUS_DONE: "已完成",
    SALES_OUT_STATUS_CANCELLED: "已作废",
}


def sales_out_status_text(status: int | None) -> str:
    """状态值转中文名，未知状态返回「未知状态」。"""
    if status is None:
        return "未知状态"
    return SALES_OUT_STATUS_TEXT.get(int(status), "未知状态")


class SalesOut(Base, TimestampMixin):
    """出库单主表（契约 9.2）。"""

    __tablename__ = "sales_out"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    no: Mapped[str] = mapped_column(
        String(32), unique=True, nullable=False, comment="单号 OUT+yyyyMMdd+4位流水"
    )
    order_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("sales_order.id"), nullable=False, comment="关联销售订单 id"
    )
    order_no: Mapped[str] = mapped_column(String(32), nullable=False, comment="冗余订单号")
    warehouse_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("warehouse.id"), nullable=False, index=True, comment="出库仓库 id"
    )
    status: Mapped[int] = mapped_column(
        TINYINT,
        nullable=False,
        default=SALES_OUT_STATUS_DRAFT,
        comment="10 草稿 / 20 已完成 / 90 已作废",
    )
    total_count: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), nullable=False, default=Decimal("0.00"), comment="总数量"
    )
    total_price: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), nullable=False, default=Decimal("0.00"), comment="总金额"
    )
    express_no: Mapped[str | None] = mapped_column(String(64), nullable=True, comment="物流单号")
    remark: Mapped[str | None] = mapped_column(String(500), nullable=True, comment="备注")
    created_by: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("sys_user.id"), nullable=False, index=True, comment="创建人 user_id"
    )

    items: Mapped[list["SalesOutItem"]] = relationship(
        back_populates="out", cascade="all, delete-orphan", lazy="selectin"
    )


class SalesOutItem(Base, TimestampMixin):
    """出库明细（契约 9.2）。"""

    __tablename__ = "sales_out_item"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    out_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("sales_out.id"), nullable=False, index=True, comment="关联 sales_out"
    )
    order_item_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("sales_order_item.id"),
        nullable=False,
        index=True,
        comment="关联 sales_order_item",
    )
    sku_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("product_sku.id"), nullable=False, index=True, comment="SKU id"
    )
    count: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), nullable=False, default=Decimal("0.00"), comment="出库数量"
    )
    price: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), nullable=False, default=Decimal("0.00"), comment="单价"
    )
    total_price: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), nullable=False, default=Decimal("0.00"), comment="小计"
    )

    out: Mapped["SalesOut"] = relationship(back_populates="items")
