import unittest
from pydantic import ValidationError

from app.schemas.stock import InventoryInboundIn


class InventoryInboundQuantityTest(unittest.TestCase):
    def test_quantity_must_be_positive_integer(self):
        payload = InventoryInboundIn(sku_id=1, warehouse_id=1, quantity=1)

        self.assertEqual(payload.quantity, 1)

        with self.assertRaises(ValidationError):
            InventoryInboundIn(sku_id=1, warehouse_id=1, quantity=1.5)

        with self.assertRaises(ValidationError):
            InventoryInboundIn(sku_id=1, warehouse_id=1, quantity=1.0)

        with self.assertRaises(ValidationError):
            InventoryInboundIn(sku_id=1, warehouse_id=1, quantity=0)

        with self.assertRaises(ValidationError):
            InventoryInboundIn(sku_id=1, warehouse_id=1, quantity=-1)


if __name__ == '__main__':
    unittest.main()
