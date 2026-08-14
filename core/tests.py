from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase
from django.urls import reverse
from django.utils import timezone

from .models import (
    Device,
    DeviceThresholdTransaction,
    Item,
    ItemTransaction,
    Notification,
    WasteReversalRequest,
)
from .notification_services import generate_expiration_notifications
from .services import (
    ItemAlreadyAvailableError,
    ItemAlreadyWastedError,
    ItemUnavailableError,
    ReversalError,
    ThresholdError,
    record_item_removal,
    record_stock_in,
    request_waste_reversal,
    review_waste_reversal,
    update_device_threshold,
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

    def test_item_cannot_be_logged_as_waste_twice_without_a_reversal(self):
        record_item_removal(
            udi=self.item.item_no,
            actor=self.user,
            is_waste=True,
        )

        with self.assertRaisesMessage(
            ItemAlreadyWastedError,
            "This item is already recorded as waste.",
        ):
            record_item_removal(
                udi=self.item.item_no,
                actor=self.user,
                is_waste=True,
            )

        self.assertEqual(
            ItemTransaction.objects.filter(
                item=self.item,
                event_type=ItemTransaction.EventType.WASTE,
            ).count(),
            1,
        )

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

        second_waste = record_item_removal(
            udi=self.item.item_no,
            actor=self.user,
            is_waste=True,
        )
        self.assertEqual(second_waste.event_type, ItemTransaction.EventType.WASTE)

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


class NotificationServiceTests(InventoryTestCase):
    def _add_second_available_item(self):
        item = Item.objects.create(
            item="Example Item",
            item_no="UDI-002",
            mfr="Example Manufacturer",
            mfr_cat="CAT-001",
            descr="Another physical inventory item",
            device=self.device,
            is_available=True,
        )
        self.device.current_count = 2
        self.device.save(update_fields=["current_count"])
        return item

    def test_low_stock_crossing_notifies_existing_active_users_and_resolves(self):
        self._add_second_available_item()

        with self.captureOnCommitCallbacks(execute=True):
            record_item_removal(udi=self.item.item_no, actor=self.user)

        notifications = Notification.objects.filter(kind=Notification.Kind.LOW_STOCK)
        self.assertEqual(notifications.count(), 3)
        self.assertSetEqual(
            set(notifications.values_list("recipient__username", flat=True)),
            {"inventory-user", "inventory-staff", "other-inventory-staff"},
        )

        with self.captureOnCommitCallbacks(execute=True):
            record_stock_in(item=self.item, actor=self.user)

        self.assertFalse(
            Notification.objects.filter(
                kind=Notification.Kind.LOW_STOCK,
                resolved_at__isnull=True,
            ).exists()
        )

    def test_manual_threshold_change_is_audited_and_staff_only(self):
        self.device.current_count = 2
        self.device.save(update_fields=["current_count"])

        with self.assertRaises(ThresholdError):
            update_device_threshold(
                device_id=self.device.pk,
                threshold=2,
                actor=self.user,
            )

        with self.captureOnCommitCallbacks(execute=True):
            change = update_device_threshold(
                device_id=self.device.pk,
                threshold=2,
                actor=self.staff_user,
                reason="Expected usage increased",
            )

        self.device.refresh_from_db()
        self.assertEqual(self.device.low_stock_threshold, 2)
        self.assertEqual(change.previous_threshold, 1)
        self.assertEqual(change.new_threshold, 2)
        self.assertEqual(change.changed_by, self.staff_user)
        self.assertEqual(DeviceThresholdTransaction.objects.count(), 1)
        self.assertEqual(
            Notification.objects.filter(kind=Notification.Kind.LOW_STOCK).count(),
            3,
        )

    def test_expiration_generation_is_idempotent_and_does_not_backfill_new_users(self):
        self.item.exp_date = timezone.localdate() + timedelta(days=30)
        self.item.save(update_fields=["exp_date"])

        self.assertEqual(generate_expiration_notifications(), 3)
        self.assertEqual(generate_expiration_notifications(), 0)

        late_user = get_user_model().objects.create_user(username="late-user")
        self.assertEqual(generate_expiration_notifications(), 0)
        self.assertFalse(Notification.objects.filter(recipient=late_user).exists())

    def test_expired_item_alert_is_generated_at_zero_days(self):
        self.item.exp_date = timezone.localdate()
        self.item.save(update_fields=["exp_date"])

        generate_expiration_notifications()

        self.assertEqual(
            Notification.objects.filter(kind=Notification.Kind.EXPIRED_ITEM).count(),
            3,
        )

        with self.captureOnCommitCallbacks(execute=True):
            record_item_removal(udi=self.item.item_no, actor=self.user)
        self.assertFalse(
            Notification.objects.filter(
                kind=Notification.Kind.EXPIRED_ITEM,
                resolved_at__isnull=True,
            ).exists()
        )

    def test_expiration_alerts_are_generated_at_every_required_milestone(self):
        expiration_date = timezone.localdate() + timedelta(days=30)
        self.item.exp_date = expiration_date
        self.item.save(update_fields=["exp_date"])

        for days_remaining in (30, 14, 7, 1, 0):
            delivered = generate_expiration_notifications(
                today=expiration_date - timedelta(days=days_remaining)
            )
            self.assertEqual(delivered, 3)

        self.assertEqual(Notification.objects.count(), 15)
        self.assertEqual(
            Notification.objects.filter(kind=Notification.Kind.EXPIRED_ITEM).count(),
            3,
        )

    def test_waste_reversal_notifications_follow_review_permissions(self):
        waste_transaction = record_item_removal(
            udi=self.item.item_no,
            actor=self.user,
            is_waste=True,
        )
        with self.captureOnCommitCallbacks(execute=True):
            reversal_request = request_waste_reversal(
                transaction_id=waste_transaction.pk,
                requested_by=self.user,
            )

        review_notifications = Notification.objects.filter(
            kind=Notification.Kind.WASTE_REVERSAL_REQUESTED
        )
        self.assertSetEqual(
            set(review_notifications.values_list("recipient_id", flat=True)),
            {self.staff_user.pk, self.other_staff_user.pk},
        )

        with self.captureOnCommitCallbacks(execute=True):
            review_waste_reversal(
                request_id=reversal_request.pk,
                reviewer=self.staff_user,
                approve=True,
            )

        resolution = Notification.objects.get(
            kind=Notification.Kind.WASTE_REVERSAL_APPROVED
        )
        self.assertEqual(resolution.recipient, self.user)
        self.assertFalse(review_notifications.filter(resolved_at__isnull=True).exists())


class InventoryBrowserTests(InventoryTestCase):
    def test_threshold_update_endpoint_requires_staff(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("update-device-threshold", args=[self.device.pk]),
            {"threshold": 4, "reason": "Testing"},
        )
        self.assertEqual(response.status_code, 403)

        self.client.force_login(self.staff_user)
        device_page = self.client.get(reverse("device-details"))
        self.assertContains(device_page, "Update Threshold Count")
        self.assertContains(device_page, "Update Threshold")

        response = self.client.post(
            reverse("update-device-threshold", args=[self.device.pk]),
            {"threshold": 4, "reason": "Testing"},
        )
        self.assertEqual(response.status_code, 302)
        self.device.refresh_from_db()
        self.assertEqual(self.device.low_stock_threshold, 4)

    def test_notification_read_dismiss_and_clear_are_scoped_to_current_user(self):
        own_notification = Notification.objects.create(
            recipient=self.user,
            kind=Notification.Kind.LOW_STOCK,
            severity=Notification.Severity.WARNING,
            title="Own alert",
            message="Own message",
            event_key="own-event",
        )
        second_own_notification = Notification.objects.create(
            recipient=self.user,
            kind=Notification.Kind.EXPIRING_ITEM,
            severity=Notification.Severity.WARNING,
            title="Second own alert",
            message="Second own message",
            event_key="second-own-event",
        )
        other_notification = Notification.objects.create(
            recipient=self.staff_user,
            kind=Notification.Kind.LOW_STOCK,
            severity=Notification.Severity.WARNING,
            title="Other alert",
            message="Other message",
            event_key="other-event",
        )
        self.client.force_login(self.user)

        inbox_response = self.client.get(reverse("notifications"))
        self.assertContains(inbox_response, "Own alert")
        self.assertContains(inbox_response, "Clear all notifications?")

        self.client.post(reverse("mark-notification-read", args=[own_notification.pk]))
        own_notification.refresh_from_db()
        self.assertIsNotNone(own_notification.read_at)

        self.client.post(reverse("clear-notifications"))
        second_own_notification.refresh_from_db()
        other_notification.refresh_from_db()
        self.assertIsNotNone(second_own_notification.dismissed_at)
        self.assertIsNone(other_notification.dismissed_at)

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
