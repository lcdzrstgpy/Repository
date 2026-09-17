"""库存模型（契约 4.8 / 4.9）。一阶段仅建表，接口只读。"""

from decimal import Decimal

from sqlalchemy import BigInteger, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, TimestampMixin


class Inventory(Base, TimestampMixin):
    """库存余额。每个 SKU 在每个仓库只有一条记录。"""

    __tablename__ = "inventory"
    __table_args__ = (
        UniqueConstraint("sku_id", "warehouse_id", name="uk_inventory_sku_warehouse"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    sku_id: Mapped[int] = mapped_column(BigInteger, nullable=False, comment="SKU id")
    warehouse_id: Mapped[int] = mapped_column(BigInteger, nullable=False, comment="仓库 id")
    quantity: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), nullable=False, default=Decimal("0.00"), comment="当前库存"
    )
    reserved_quantity: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), nullable=False, default=Decimal("0.00"), comment="预留库存"
    )


class InventoryHistory(Base, TimestampMixin):
    """库存流水。一阶段建表但不写入。"""

    __tablename__ = "inventory_history"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    sku_id: Mapped[int] = mapped_column(BigInteger, nullable=False, comment="SKU id")
    warehouse_id: Mapped[int] = mapped_column(BigInteger, nullable=False, comment="仓库 id")
    quantity: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), nullable=False, default=Decimal("0.00"), comment="变动量，正入负出"
    )
    before_quantity: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), nullable=False, default=Decimal("0.00"), comment="变动前"
    )
    after_quantity: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), nullable=False, default=Decimal("0.00"), comment="变动后"
    )
    order_no: Mapped[str | None] = mapped_column(String(32), nullable=True, comment="关联单号")
    order_type: Mapped[str | None] = mapped_column(String(20), nullable=True, comment="单据类型")
    created_by: Mapped[int | None] = mapped_column(BigInteger, nullable=True, comment="操作人")
    remark: Mapped[str | None] = mapped_column(String(500), nullable=True, comment="备注")
