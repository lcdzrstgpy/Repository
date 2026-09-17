"""基础数据 CRUD 的请求 schema（契约 5.2）。

新增用 *Create，修改用 *Update（字段全部可选，做部分更新）。
"""

from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field

# 通用状态：1 启用 / 0 停用
StatusField = Literal[0, 1]

# 用户角色（契约 3.1）
RoleField = Literal["admin", "operator", "warehouse", "approver"]


# ---------------------------------------------------------------- 仓库
class WarehouseCreate(BaseModel):
    """新增仓库。"""

    code: str = Field(..., min_length=1, max_length=32, description="仓库编码")
    name: str = Field(..., min_length=1, max_length=100, description="仓库名称")
    address: str | None = Field(None, max_length=255, description="地址")
    status: StatusField = Field(1, description="1 启用 / 0 停用")


class WarehouseUpdate(BaseModel):
    """修改仓库。"""

    code: str | None = Field(None, min_length=1, max_length=32)
    name: str | None = Field(None, min_length=1, max_length=100)
    address: str | None = Field(None, max_length=255)
    status: StatusField | None = None


# ---------------------------------------------------------------- 商品
class ProductCreate(BaseModel):
    """新增商品。"""

    code: str = Field(..., min_length=1, max_length=64, description="商品编码")
    name: str = Field(..., min_length=1, max_length=200, description="商品名称")
    category: str | None = Field(None, max_length=50, description="分类")
    unit: str | None = Field(None, max_length=20, description="单位")
    status: StatusField = Field(1, description="1 启用 / 0 停用")


class ProductUpdate(BaseModel):
    """修改商品。"""

    code: str | None = Field(None, min_length=1, max_length=64)
    name: str | None = Field(None, min_length=1, max_length=200)
    category: str | None = Field(None, max_length=50)
    unit: str | None = Field(None, max_length=20)
    status: StatusField | None = None


# ---------------------------------------------------------------- SKU
class SkuCreate(BaseModel):
    """新增 SKU。"""

    product_id: int = Field(..., gt=0, description="关联商品 id")
    sku_code: str = Field(..., min_length=1, max_length=64, description="SKU 编码")
    spec: str | None = Field(None, max_length=200, description="规格")
    image_url: str | None = Field(None, max_length=500, description="SKU 图片地址")
    remark: str | None = Field(None, max_length=500, description="SKU 备注")
    price: Decimal = Field(Decimal("0.00"), ge=0, description="售价")
    min_stock: Decimal = Field(Decimal("0.00"), ge=0, description="安全库存下限，0 表示不预警")
    status: StatusField = Field(1, description="1 启用 / 0 停用")


class SkuUpdate(BaseModel):
    """修改 SKU。"""

    product_id: int | None = Field(None, gt=0)
    sku_code: str | None = Field(None, min_length=1, max_length=64)
    spec: str | None = Field(None, max_length=200)
    image_url: str | None = Field(None, max_length=500)
    remark: str | None = Field(None, max_length=500)
    price: Decimal | None = Field(None, ge=0)
    min_stock: Decimal | None = Field(None, ge=0)
    status: StatusField | None = None


# ---------------------------------------------------------------- 往来单位
class PartnerCreate(BaseModel):
    """新增往来单位。"""

    name: str = Field(..., min_length=1, max_length=200, description="名称")
    type: Literal[1, 2, 3] = Field(1, description="1 客户 / 2 供应商 / 3 两者都是")
    contact: str | None = Field(None, max_length=50, description="联系人")
    phone: str | None = Field(None, max_length=30, description="电话")
    address: str | None = Field(None, max_length=255, description="地址")
    status: StatusField = Field(1, description="1 启用 / 0 停用")


class PartnerUpdate(BaseModel):
    """修改往来单位。"""

    name: str | None = Field(None, min_length=1, max_length=200)
    type: Literal[1, 2, 3] | None = None
    contact: str | None = Field(None, max_length=50)
    phone: str | None = Field(None, max_length=30)
    address: str | None = Field(None, max_length=255)
    status: StatusField | None = None


# ---------------------------------------------------------------- 用户
class UserCreate(BaseModel):
    """新增用户，password 明文传入，后端 bcrypt 哈希存储。"""

    username: str = Field(..., min_length=1, max_length=50, description="登录名")
    password: str = Field(..., min_length=6, max_length=128, description="密码，至少 6 位")
    real_name: str | None = Field(None, max_length=50, description="姓名")
    role: RoleField = Field("operator", description="角色")
    status: StatusField = Field(1, description="1 启用 / 0 停用")


class UserUpdate(BaseModel):
    """修改用户，password 不传表示不修改密码。"""

    username: str | None = Field(None, min_length=1, max_length=50)
    password: str | None = Field(None, min_length=6, max_length=128)
    real_name: str | None = Field(None, max_length=50)
    role: RoleField | None = None
    status: StatusField | None = None
