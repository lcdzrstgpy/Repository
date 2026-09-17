import unittest

from app.schemas.purchase import PurchaseOrderCreateIn, PurchaseReceiveIn
from app.schemas.stock import InventoryInboundIn


class SingleWarehousePurchaseSchemaTest(unittest.TestCase):
    def test_procurement_and_inbound_requests_need_no_warehouse_or_supplier(self):
        purchase = PurchaseOrderCreateIn(
            sales_order_id=None,
            express_no="SF1234567890",
            items=[{"sku_id": 1, "count": 1, "price": 0}],
        )
        receive = PurchaseReceiveIn(items=[{"order_item_id": 1, "count": 1}])
        receive_with_express = PurchaseReceiveIn(
            express_no="YT1234567890", items=[{"order_item_id": 1, "count": 1}]
        )
        inbound = InventoryInboundIn(sku_id=1, quantity=1)

        self.assertEqual(purchase.express_no, "SF1234567890")
        self.assertEqual(len(receive.items), 1)
        self.assertEqual(receive_with_express.express_no, "YT1234567890")
        self.assertEqual(inbound.quantity, 1)


if __name__ == '__main__':
    unittest.main()
