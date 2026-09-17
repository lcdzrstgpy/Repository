"""Pydantic v2 请求 / 响应模型包。"""

from app.schemas.auth import LoginRequest, LoginResponse, UserInfo
from app.schemas.basic import (
    PartnerCreate,
    PartnerUpdate,
    ProductCreate,
    ProductUpdate,
    SkuCreate,
    SkuUpdate,
    UserCreate,
    UserUpdate,
    WarehouseCreate,
    WarehouseUpdate,
)
from app.schemas.order import OrderItemIn, SalesOrderCancelIn, SalesOrderCreateIn, ShipIn, ClaimIn

__all__ = [
    "LoginRequest",
    "LoginResponse",
    "UserInfo",
    "WarehouseCreate",
    "WarehouseUpdate",
    "ProductCreate",
    "ProductUpdate",
    "SkuCreate",
    "SkuUpdate",
    "PartnerCreate",
    "PartnerUpdate",
    "UserCreate",
    "UserUpdate",
    "SalesOrderCreateIn",
    "OrderItemIn",
    "SalesOrderCancelIn",
    "ClaimIn",
    "ShipIn",
]
