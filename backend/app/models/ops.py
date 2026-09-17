"""移库单 / 盘点单模型（契约 16.2 / 17.2）。

两张单据都**不在建单时动库存**（与采购单同一设计：单据与库存分离）：
移库只有「执行移库」、盘点只有「完成盘点」才通过 `change_inventory` 变更库存。
"""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, DateTime, ForeignKey, Numeric, String
from sqlalchemy.dialects.mysql import TINYINT
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, TimestampMixin

# 移库单状态值（契约 16.2）
TRANSFER_STATUS_DRAFT = 10  # 草稿
TRANSFER_STATUS_DONE = 20  # 已完成
TRANSFER_STATUS_CANCELLED = 90  # 已作废

# 状态中文名，列表/详情接口的 status_text 与流转错误提示都取自这里
TRANSFER_STATUS_TEXT: dict[int, str] = {
    TRANSFER_STATUS_DRAFT: "草稿",
    TRANSFER_STATUS_DONE: "已完成",
    TRANSFER_STATUS_CANCELLED: "已作废",
}

# 盘点单状态值（契约 17.2）
STOCK_TAKE_STATUS_DOING = 10  # 盘点中
STOCK_TAKE_STATUS_DONE = 20  # 已完成
STOCK_TAKE_STATUS_CANCELLED = 90  # 已作废

STOCK_TAKE_STATUS_TEXT: dict[int, str] = {
    STOCK_TAKE_STATUS_DOING: "盘点中",
    STOCK_TAKE_STATUS_DONE: "已完成",
    STOCK_TAKE_STATUS_CANCELLED: "已作废",
}


def transfer_status_text(status: int | None) -> str:
    """移库单状态值转中文名，未知状态返回「未知状态」。"""
    if status is None:
        return "未知状态"
    return TRANSFER_STATUS_TEXT.get(int(status), "未知状态")


def stock_take_status_text(status: int | None) -> str:
    """盘点单状态值转中文名，未知状态返回「未知状态」。"""
    if status is None:
        return "未知状态"
    return STOCK_TAKE_STATUS_TEXT.get(int(status), "未知状态")


class StockTransfer(Base, TimestampMixin):
    """移库单主表（契约 16.2）：一个出库仓 → 一个入库仓，一次可移多个 SKU。"""

    __tablename__ = "stock_transfer"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    no: Mapped[str] = mapped_column(
        String(32), unique=True, nullable=False, comment="单号 TR+yyyyMMdd+4位流水"
    )
    from_warehouse_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("warehouse.id"),
        nullable=False,
        index=True,
        comment="出库仓 warehouse.id",
    )
    to_warehouse_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("warehouse.id"),
        nullable=False,
        index=True,
        comment="入库仓 warehouse.id",
    )
    status: Mapped[int] = mapped_column(
        TINYINT,
        nullable=False,
        default=TRANSFER_STATUS_DRAFT,
        index=True,
        comment="10 草稿 / 20 已完成 / 90 已作废",
    )
    total_count: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), nullable=False, default=Decimal("0.00"), comment="合计移库数量"
    )
    remark: Mapped[str | None] = mapped_column(String(500), nullable=True, comment="备注")
    created_by: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("sys_user.id"), nullable=False, index=True, comment="制单人 user_id"
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True, comment="执行移库时间"
    )

    items: Mapped[list["StockTransferItem"]] = relationship(
        back_populates="transfer", cascade="all, delete-orphan", lazy="selectin"
    )


class StockTransferItem(Base, TimestampMixin):
    """移库单明细（契约 16.2）。"""

    __tablename__ = "stock_transfer_item"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    transfer_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("stock_transfer.id"),
        nullable=False,
        index=True,
        comment="关联 stock_transfer",
    )
    sku_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("product_sku.id"), nullable=False, index=True, comment="SKU id"
    )
    count: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), nullable=False, default=Decimal("0.00"), comment="移库数量，> 0"
    )

    transfer: Mapped["StockTransfer"] = relationship(back_populates="items")


class StockTake(Base, TimestampMixin):
    """盘点单主表（契约 17.2）。建单时快照账面数量，完成时按差异调库存。"""

    __tablename__ = "stock_take"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    no: Mapped[str] = mapped_column(
        String(32), unique=True, nullable=False, comment="单号 ST+yyyyMMdd+4位流水"
    )
    warehouse_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("warehouse.id"),
        nullable=False,
        index=True,
        comment="盘点仓库 warehouse.id",
    )
    status: Mapped[int] = mapped_column(
        TINYINT,
        nullable=False,
        default=STOCK_TAKE_STATUS_DOING,
        index=True,
        comment="10 盘点中 / 20 已完成 / 90 已作废",
    )
    total_count: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), nullable=False, default=Decimal("0.00"), comment="账面数量合计（建单时快照）"
    )
    diff_count: Mapped[Decimal] = mapped_column(
        Numeric(14, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="差异合计（实盘-账面），完成时写入，未完成时 0",
    )
    remark: Mapped[str | None] = mapped_column(String(500), nullable=True, comment="备注")
    created_by: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("sys_user.id"), nullable=False, index=True, comment="制单人 user_id"
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True, comment="完成盘点时间"
    )

    items: Mapped[list["StockTakeItem"]] = relationship(
        back_populates="stock_take", cascade="all, delete-orphan", lazy="selectin"
    )


class StockTakeItem(Base, TimestampMixin):
    """盘点单明细（契约 17.2）。建单时 actual_quantity = book_quantity，完成时写 diff_quantity。"""

    __tablename__ = "stock_take_item"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    stock_take_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("stock_take.id"),
        nullable=False,
        index=True,
        comment="关联 stock_take",
    )
    sku_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("product_sku.id"), nullable=False, index=True, comment="SKU id"
    )
    book_quantity: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), nullable=False, default=Decimal("0.00"), comment="账面数量（建单快照）"
    )
    actual_quantity: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), nullable=False, default=Decimal("0.00"), comment="实盘数量，建单时=账面数量"
    )
    diff_quantity: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), nullable=False, default=Decimal("0.00"), comment="差异=实盘-账面，完成时写入"
    )
    remark: Mapped[str | None] = mapped_column(String(255), nullable=True, comment="行备注")

    stock_take: Mapped["StockTake"] = relationship(back_populates="items")
