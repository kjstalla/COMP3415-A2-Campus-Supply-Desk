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

    # newly added tests for express delivery

    def test_showing_express_delivery_quote(self):
        quote = self.service.quote("regular", [{"product_id": "notebook", "quantity": 2}], "express")
        self.assertEqual(quote["subtotal_cents"], 1000)
        self.assertEqual(quote["discount_cents"], 0)
        self.assertEqual(quote["delivery_cents"], 1200)
        self.assertEqual(quote["total_cents"], 2200)

    def test_verify_student_discount_with_express(self):
        quote = self.service.quote("student", [{"product_id": "hoodie", "quantity": 2}], "express")
        self.assertEqual(quote["subtotal_cents"], 8000)
        self.assertEqual(quote["discount_cents"], 800)
        self.assertEqual(quote["delivery_cents"], 1200)
        self.assertEqual(quote["total_cents"], 8400)

    def test_express_fee_not_waived(self):
        quote1 = self.service.quote("regular", [{"product_id": "hoodie", "quantity": 3}], "delivery")
        quote2 = self.service.quote("regular", [{"product_id": "hoodie", "quantity": 3}], "express")
        self.assertEqual(quote1["delivery_cents"], 0)
        self.assertEqual(quote2["delivery_cents"], 1200)
        
    def test_wrong_fulfillment_causes_error(self):
        with self.assertRaises(ValueError):
            self.service.quote("regular", [{"product_id": "hoodie", "quantity": 2}], "test_fulfillment")

    def test_express_orders_persist(self):
        order = self.service.place_order("regular", [{"product_id": "pen-pack", "quantity": 3}], "express")
        self.assertEqual(order["subtotal_cents"], 2250)
        self.assertEqual(order["discount_cents"], 0)
        self.assertEqual(order["delivery_cents"], 1200)
        self.assertEqual(order["total_cents"], 3450)
        open_service = OrderService(self.path)
        open_order = open_service.get_order(order["order_id"])

        self.assertEqual(open_order["fulfillment"], "express")
        self.assertEqual(open_order["items"], order["items"])
        self.assertEqual(open_order["subtotal_cents"], 2250)
        self.assertEqual(open_order["discount_cents"],  0)
        self.assertEqual(open_order["delivery_cents"], 1200)
        self.assertEqual(open_order["total_cents"], 3450)
        self.assertEqual(open_order, order)

    def test_express_order_cancellation(self):
        before = self.service.catalog()
        order = self.service.place_order("regular", [{"product_id": "pen-pack", "quantity": 2}], "express")
        cancelled = self.service.cancel_order(order["order_id"])
        self.assertEqual(cancelled["status"], "cancelled")
        self.assertEqual(self.service.catalog(), before)

        self.assertEqual(cancelled["fulfillment"], "express")
        self.assertEqual(cancelled["items"], order["items"])
        self.assertEqual(cancelled["delivery_cents"], order["delivery_cents"])
        self.assertEqual(cancelled["discount_cents"], order["discount_cents"])
        self.assertEqual(cancelled["total_cents"], order["total_cents"])

    def test_verify_student_does_not_get_discount_below_threshold(self):
        quote = self.service.quote("student", [{"product_id": "pen-pack", "quantity": 1}, {"product_id": "hoodie", "quantity": 1}])
        self.assertEqual(quote["subtotal_cents"], 4750)
        self.assertEqual(quote["discount_cents"], 0)
        self.assertEqual(quote["delivery_cents"], 0)
        self.assertEqual(quote["total_cents"], 4750)
if __name__ == "__main__":
    unittest.main()
