"""A small starting test suite for the order desk."""

from pathlib import Path
import tempfile
import unittest

from supplydesk.service import OrderService

class OrderSmokeTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "state.json"
        self.service = OrderService(self.path)

    def test_regular_pickup_quote(self):
        quote = self.service.quote("regular", [{"product_id": "notebook", "quantity": 2}])
        self.assertEqual(quote["subtotal_cents"], 1000)
        self.assertEqual(quote["discount_cents"], 0)
        self.assertEqual(quote["delivery_cents"], 0)
        self.assertEqual(quote["total_cents"], 1000)

    def test_student_delivery_quote(self):
        quote = self.service.quote("student", [{"product_id": "hoodie", "quantity": 2}], "delivery")
        self.assertEqual(quote["discount_cents"], 800)
        self.assertEqual(quote["delivery_cents"], 600)
        self.assertEqual(quote["total_cents"], 7800)

    def test_order_can_be_reopened(self):
        order = self.service.place_order("regular", [{"product_id": "mug", "quantity": 1}])
        self.assertEqual(order["order_id"], "ORD-0001")
        self.assertEqual(order["status"], "placed")
        self.assertEqual(OrderService(self.path).get_order(order["order_id"]), order)

    def test_cancel_order_restores_stock(self):
        before = self.service.catalog()
        order = self.service.place_order("regular", [{"product_id": "pen-pack", "quantity": 2}])
        cancelled = self.service.cancel_order(order["order_id"])
        self.assertEqual(cancelled["status"], "cancelled")
        self.assertEqual(self.service.catalog(), before)

    # normal bahaviour test 
    def test_place_order_and_verify_stock(self):
        inventory = self.service.catalog()

        findNotebook = next(
            item for item in inventory
            if item["product_id"] == "notebook"
        )

        numberOfNotebooks = findNotebook["stock"]
        self.service.place_order("regular", [{"product_id": "notebook", "quantity": 2}])

        newInventory = self.service.catalog()
        newNumberOfNotebooks = next(
            item for item in newInventory
            if item["product_id"] == "notebook"
        )

        self.assertEqual(newNumberOfNotebooks["stock"], numberOfNotebooks - 2)

    # boundary test
    def test_student_discount_baseline(self):
        quote = self.service.quote("student", [{"product_id": "bag", "quantity": 2}])
        self.assertEqual(quote["discount_cents"], 500)
        
    # invalid behaviour tests
    def test_stock_is_less_than_ordered(self):
        inventory = self.service.catalog()

        hoodie = next(
            item for item in inventory 
            if item["product_id"] == "hoodie"
        ) 

        numberOfHoodies = hoodie["stock"]

        with self.assertRaises(ValueError):
            self.service.quote("regular", [{"product_id": "hoodie", "quantity": numberOfHoodies + 1}])

    def test_user_orders_nothing(self):
        with self.assertRaises(ValueError):
            self.service.quote("regular", [{"product_id": "hoodie", "quantity": 0}])

    # preservation tests
    
    def test_stock_is_preserved_on_quote(self):
        inventory = self.service.catalog()
        self.service.quote("regular", [{"product_id": "notebook", "quantity": 2}])
        self.assertEqual(self.service.catalog(), inventory)

    def test_cancelling_cancelled_order_preserves_stock (self):
        before = self.service.catalog()
        order = self.service.place_order("regular", [{"product_id": "pen-pack", "quantity": 2}])
        cancelled = self.service.cancel_order(order["order_id"])
        self.assertEqual(cancelled["status"], "cancelled")
        self.assertEqual(self.service.catalog(), before)
        secondCancelled = self.service.cancel_order(order["order_id"])
        self.assertEqual(secondCancelled["status"], "cancelled")
        after = self.service.catalog()
        self.assertEqual(after, before)
        
if __name__ == "__main__":
    unittest.main()
