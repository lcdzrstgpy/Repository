"""基础数据模型：仓库、商品、SKU、往来单位（契约 4.2 ~ 4.5）。"""

from decimal import Decimal

from sqlalchemy import BigInteger, ForeignKey, Numeric, String
from sqlalchemy.dialects.mysql import TINYINT
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, TimestampMixin

# 往来单位类型中文名（契约 3.4）
PARTNER_TYPE_TEXT: dict[int, str] = {1: "客户", 2: "供应商", 3: "两者都是"}


class Warehouse(Base, TimestampMixin):
    """仓库（契约 4.2）。"""

    __tablename__ = "warehouse"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False, comment="仓库编码")
    name: Mapped[str] = mapped_column(String(100), nullable=False, comment="仓库名称")
    address: Mapped[str | None] = mapped_column(String(255), nullable=True, comment="地址")
    status: Mapped[int] = mapped_column(
        TINYINT, nullable=False, default=1, comment="1 启用 / 0 停用"
    )


class Product(Base, TimestampMixin):
    """商品（契约 4.3）。"""

    __tablename__ = "product"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, comment="商品编码")
    name: Mapped[str] = mapped_column(String(200), nullable=False, comment="商品名称")
    category: Mapped[str | None] = mapped_column(String(50), nullable=True, comment="分类")
    unit: Mapped[str | None] = mapped_column(String(20), nullable=True, comment="单位")
    status: Mapped[int] = mapped_column(
        TINYINT, nullable=False, default=1, comment="1 启用 / 0 停用"
    )


class ProductCategory(Base, TimestampMixin):
    """货号三级分类。code_segment 为本层展示编码，如 A001。"""

    __tablename__ = "product_category"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    parent_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, index=True)
    level: Mapped[int] = mapped_column(TINYINT, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    code_segment: Mapped[str] = mapped_column(String(8), nullable=False)


class ProductSku(Base, TimestampMixin):
    """商品 SKU（契约 4.4）。"""

    __tablename__ = "product_sku"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    product_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("product.id"), nullable=False, comment="关联 product"
    )
    category_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, index=True)
    sku_code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, comment="SKU 编码")
    spec: Mapped[str | None] = mapped_column(String(200), nullable=True, comment="规格")
    image_url: Mapped[str | None] = mapped_column(String(500), nullable=True, comment="SKU 图片地址")
    remark: Mapped[str | None] = mapped_column(String(500), nullable=True, comment="SKU 备注")
    price: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), nullable=False, default=Decimal("0.00"), comment="售价"
    )
    min_stock: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), nullable=False, default=Decimal("0.00"), comment="安全库存下限，0 表示不预警"
    )
    status: Mapped[int] = mapped_column(
        TINYINT, nullable=False, default=1, comment="1 启用 / 0 停用"
    )


class Partner(Base, TimestampMixin):
    """往来单位：客户 / 供应商一表两用（契约 4.5）。"""

    __tablename__ = "partner"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    name: Mapped[str] = mapped_column(String(200), nullable=False, comment="名称")
    type: Mapped[int] = mapped_column(
        TINYINT, nullable=False, default=1, comment="1 客户 / 2 供应商 / 3 两者都是"
    )
    contact: Mapped[str | None] = mapped_column(String(50), nullable=True, comment="联系人")
    phone: Mapped[str | None] = mapped_column(String(30), nullable=True, comment="电话")
    address: Mapped[str | None] = mapped_column(String(255), nullable=True, comment="地址")
    status: Mapped[int] = mapped_column(
        TINYINT, nullable=False, default=1, comment="1 启用 / 0 停用"
    )
