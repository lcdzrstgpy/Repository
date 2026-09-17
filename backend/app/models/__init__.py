"""SQLAlchemy 模型包。导入全部模型，保证 Base.metadata 完整。"""

from app.models.basic import Partner, Product, ProductCategory, ProductSku, Warehouse
from app.models.inventory import Inventory, InventoryHistory
from app.models.ops import (
    STOCK_TAKE_STATUS_TEXT,
    TRANSFER_STATUS_TEXT,
    StockTake,
    StockTakeItem,
    StockTransfer,
    StockTransferItem,
)
from app.models.order import (
    ORDER_STATUS_CANCELLED,
    ORDER_STATUS_TEXT,
    SalesOrder,
    SalesOrderItem,
)
from app.models.purchase import (
    PURCHASE_IN_STATUS_TEXT,
    PURCHASE_STATUS_TEXT,
    PurchaseIn,
    PurchaseInItem,
    PurchaseOrder,
    PurchaseOrderItem,
)
from app.models.stock import (
    SALES_OUT_STATUS_TEXT,
    SalesOut,
    SalesOutItem,
)
from app.models.user import ROLE_TEXT, SysUser

__all__ = [
    "SysUser",
    "ROLE_TEXT",
    "Warehouse",
    "Product",
    "ProductCategory",
    "ProductSku",
    "Partner",
    "SalesOrder",
    "SalesOrderItem",
    "ORDER_STATUS_TEXT",
    "ORDER_STATUS_CANCELLED",
    "Inventory",
    "InventoryHistory",
    "SalesOut",
    "SalesOutItem",
    "SALES_OUT_STATUS_TEXT",
    "PurchaseOrder",
    "PurchaseOrderItem",
    "PurchaseIn",
    "PurchaseInItem",
    "PURCHASE_STATUS_TEXT",
    "PURCHASE_IN_STATUS_TEXT",
    "StockTransfer",
    "StockTransferItem",
    "StockTake",
    "StockTakeItem",
    "TRANSFER_STATUS_TEXT",
    "STOCK_TAKE_STATUS_TEXT",
]
