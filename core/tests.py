from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Device, Item, ItemTransaction, WasteReversalRequest
from .services import (
    ItemAlreadyAvailableError,
    ItemUnavailableError,
    ReversalError,
    record_item_removal,
    record_stock_in,
    request_waste_reversal,
    review_waste_reversal,
)
from .views import HomePageView, WasteLogView


class InventoryTestCase(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.user = user_model.objects.create_user(
            username="inventory-user", password="test-password"
        )
        self.staff_user = user_model.objects.create_user(
            username="inventory-staff",
            password="test-password",
            is_staff=True,
        )
        self.other_staff_user = user_model.objects.create_user(
            username="other-inventory-staff",
            password="test-password",
            is_staff=True,
        )
        self.device = Device.objects.create(
            manufacturer="Example Manufacturer",
            device_name="Example Device",
            device_identifier="DI-001",
            current_count=1,
        )
        self.item = Item.objects.create(
            item="Example Item",
            item_no="UDI-001",
            mfr="Example Manufacturer",
            mfr_cat="CAT-001",
            descr="One physical inventory item",
            device=self.device,
            is_available=True,
        )


class InventoryServiceTests(InventoryTestCase):
    def test_waste_removal_records_exact_item_and_decrements_device(self):
        occurred_at = timezone.now() - timedelta(days=2)

        inventory_transaction = record_item_removal(
            udi=self.item.item_no,
            actor=self.user,
            is_waste=True,
            occurred_at=occurred_at,
            notes="Expired before use",
            estimated_cost=Decimal("15.50"),
        )

        self.item.refresh_from_db()
        self.device.refresh_from_db()
        self.assertFalse(self.item.is_available)
        self.assertEqual(self.device.current_count, 0)
        self.assertEqual(inventory_transaction.item, self.item)
        self.assertEqual(
            inventory_transaction.event_type, ItemTransaction.EventType.WASTE
        )
        self.assertEqual(inventory_transaction.change, -1)
        self.assertEqual(inventory_transaction.occurred_at, occurred_at)
        self.assertEqual(inventory_transaction.created_by, self.user)
        self.assertEqual(inventory_transaction.estimated_cost, Decimal("15.50"))

    def test_unavailable_item_cannot_be_removed_again(self):
        record_item_removal(udi=self.item.item_no, actor=self.user)

        with self.assertRaises(ItemUnavailableError):
            record_item_removal(
                udi=self.item.item_no,
                actor=self.user,
                is_waste=True,
            )

        self.device.refresh_from_db()
        self.assertEqual(self.device.current_count, 0)
        self.assertEqual(ItemTransaction.objects.count(), 1)

    def test_stock_in_restores_one_item_but_cannot_duplicate_it(self):
        self.item.is_available = False
        self.item.save(update_fields=["is_available"])
        self.device.current_count = 0
        self.device.save(update_fields=["current_count"])

        inventory_transaction = record_stock_in(item=self.item, actor=self.user)

        self.item.refresh_from_db()
        self.device.refresh_from_db()
        self.assertTrue(self.item.is_available)
        self.assertEqual(self.device.current_count, 1)
        self.assertEqual(inventory_transaction.change, 1)
        with self.assertRaises(ItemAlreadyAvailableError):
            record_stock_in(item=self.item, actor=self.user)

    def test_approved_reversal_restores_item_with_linked_transaction(self):
        waste_transaction = record_item_removal(
            udi=self.item.item_no,
            actor=self.user,
            is_waste=True,
        )
        reversal_request = request_waste_reversal(
            transaction_id=waste_transaction.id,
            requested_by=self.user,
            reason="Recorded against the wrong item",
        )

        reversal = review_waste_reversal(
            request_id=reversal_request.id,
            reviewer=self.staff_user,
            approve=True,
        )

        self.item.refresh_from_db()
        self.device.refresh_from_db()
        reversal_request.refresh_from_db()
        self.assertTrue(self.item.is_available)
        self.assertEqual(self.device.current_count, 1)
        self.assertEqual(
            reversal.event_type, ItemTransaction.EventType.WASTE_REVERSAL
        )
        self.assertEqual(reversal.reversal_of, waste_transaction)
        self.assertEqual(reversal.created_by, self.staff_user)
        self.assertEqual(
            reversal_request.status, WasteReversalRequest.Status.APPROVED
        )

    def test_requester_cannot_approve_own_reversal(self):
        waste_transaction = record_item_removal(
            udi=self.item.item_no,
            actor=self.staff_user,
            is_waste=True,
        )
        reversal_request = request_waste_reversal(
            transaction_id=waste_transaction.id,
            requested_by=self.staff_user,
        )

        with self.assertRaises(ReversalError):
            review_waste_reversal(
                request_id=reversal_request.id,
                reviewer=self.staff_user,
                approve=True,
            )

        reversal = review_waste_reversal(
            request_id=reversal_request.id,
            reviewer=self.other_staff_user,
            approve=True,
        )
        self.assertIsNotNone(reversal)


class InventoryBrowserTests(InventoryTestCase):
    def test_device_links_to_item_page_filtered_to_that_device(self):
        other_device = Device.objects.create(
            manufacturer="Other Manufacturer",
            device_name="Other Device",
            device_identifier="DI-OTHER",
        )
        Item.objects.create(
            item="Other Item",
            item_no="UDI-OTHER",
            mfr="Other Manufacturer",
            mfr_cat="CAT-OTHER",
            descr="A different device type",
            device=other_device,
            is_available=True,
        )

        device_response = self.client.get(reverse("device-details"))
        item_url = f'{reverse("item-details")}?device={self.device.pk}'
        self.assertContains(device_response, item_url)

        item_response = self.client.get(item_url)
        self.assertEqual(item_response.status_code, 200)
        self.assertContains(item_response, self.item.item_no)
        self.assertNotContains(item_response, "UDI-OTHER")
        self.assertContains(item_response, self.device.device_identifier)

    def test_item_transaction_page_handles_empty_history(self):
        response = self.client.get(reverse("itemtransaction-details"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "No item transactions available yet.")

    def test_order_page_handles_empty_history(self):
        response = self.client.get(reverse("order-details"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "No orders available yet.")

    def test_home_page_links_reversal_requests_to_waste_log(self):
        request = RequestFactory().get(reverse("home"))
        request.user = self.user
        response = HomePageView.as_view()(request)
        response.render()

        content = response.content.decode()
        self.assertEqual(response.status_code, 200)
        self.assertIn(reverse("waste-log"), content)
        self.assertIn("Waste Log", content)
        self.assertNotIn("Waste Reversal Requests", content)

    def test_existing_remove_workflow_records_waste(self):
        self.client.force_login(self.user)
        occurred_at = (timezone.localtime() - timedelta(days=1)).strftime(
            "%Y-%m-%dT%H:%M"
        )

        response = self.client.post(
            reverse("add_remove_items_by_barcode"),
            {
                "barcode": self.item.item_no,
                "add_remove": "out",
                "is_waste": "on",
                "occurred_at": occurred_at,
                "notes": "Damaged package",
                "estimated_cost": "12.25",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.item.refresh_from_db()
        self.assertFalse(self.item.is_available)
        waste_transaction = ItemTransaction.objects.get()
        self.assertEqual(
            waste_transaction.event_type, ItemTransaction.EventType.WASTE
        )
        self.assertEqual(waste_transaction.item, self.item)
        self.assertEqual(waste_transaction.change, -1)

    def test_waste_log_requires_login_and_displays_waste(self):
        waste_transaction = record_item_removal(
            udi=self.item.item_no,
            actor=self.user,
            is_waste=True,
        )

        anonymous_response = self.client.get(reverse("waste-log"))
        self.assertEqual(anonymous_response.status_code, 302)

        request = RequestFactory().get(reverse("waste-log"))
        request.user = self.user
        response = WasteLogView.as_view()(request)
        response.render()
        self.assertEqual(response.status_code, 200)
        self.assertIn(waste_transaction.item.item_no, response.content.decode())

    def test_reversal_approval_endpoint_requires_staff(self):
        waste_transaction = record_item_removal(
            udi=self.item.item_no,
            actor=self.user,
            is_waste=True,
        )
        reversal_request = request_waste_reversal(
            transaction_id=waste_transaction.id,
            requested_by=self.user,
        )

        self.client.force_login(self.user)
        response = self.client.post(
            reverse(
                "review-waste-reversal",
                args=[reversal_request.id, "approve"],
            )
        )
        self.assertEqual(response.status_code, 403)

        self.client.force_login(self.staff_user)
        response = self.client.post(
            reverse(
                "review-waste-reversal",
                args=[reversal_request.id, "approve"],
            )
        )
        self.assertEqual(response.status_code, 302)
        reversal_request.refresh_from_db()
        self.assertEqual(
            reversal_request.status, WasteReversalRequest.Status.APPROVED
        )
