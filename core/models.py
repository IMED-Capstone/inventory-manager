"""Defines models used across the Core app."""

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from djmoney.models.fields import MoneyField


class Device(models.Model):
    manufacturer = models.CharField("MANUFACTURER", max_length=200, null=True)
    device_name = models.CharField("NAME", max_length=200,null=True)
    device_identifier = models.CharField("DI", max_length=200, unique=True)
    current_count = models.IntegerField("CURR COUNT", default=0)
    low_stock_threshold = models.PositiveIntegerField(default=1)
    
    def increase_count(self, number_change):
        self.current_count = self.current_count + number_change
        return self.current_count
    
    def decrease_count(self, number_change):
        self.current_count = self.current_count - number_change
        return self.current_count

    @property
    def quantity(self):
        return self.items.filter(is_available=True).count()
    
    def __str__(self):
        """
        Defines the string representation of the :class:`~core.models.Device`
        In this case, is defined as the `device_indentifier` field, which represents an :class:`~core.models.Device` number.
        """
        return self.device_identifier

class Item(models.Model):
    """Defines an :class:`~core.models.Item` model representing an individual item in inventory."""

    item = models.CharField("ITEM", max_length=200)
    item_no = models.CharField("ITEM_NO", max_length=200, unique=True)
    mfr = models.CharField("MFR", max_length=200)
    mfr_cat = models.CharField("MFR CAT", max_length=200)
    descr = models.CharField("DESCR", max_length=200)
    device = models.ForeignKey(Device, on_delete=models.PROTECT, related_name="items", null=True)
    is_available = models.BooleanField(default=False, db_index=True)
    exp_date = models.DateField("EXP DATE", null=True)
    external_url = models.URLField(
        max_length=200,
        default="https://accessgudid.nlm.nih.gov/resources/developers/v3/device_lookup_api",
    )

    @property
    def quantity(self):
        """
        Dynamically calculates the quantity of a given :class:`~core.models.Item` based on its transaction history.

        Returns:
            int: the number of :class:`Items <core.models.Item>` in inventory, as calculated from its transaction history.
        """
        return int(self.is_available)

    def __str__(self):
        """
        Defines the string representation of the :class:`~core.models.Item` (useful in the Admin view, but also other places where the string representation should be meaningful).
        In this case, is defined as the `item` field, which represents an :class:`~core.models.Item` number.
        """
        return self.item


class Order(models.Model):
    """
    Defines an :class:`~core.models.Order` model representing an order for an :class:`~core.models.Item` in inventory.
    """

    item = models.ForeignKey(Item, on_delete=models.PROTECT)
    vendor = models.CharField("VENDOR", max_length=200)
    vend_cat = models.CharField("VEND CAT", max_length=200)
    recv_qty = models.IntegerField("RECV QTY")
    um = models.CharField("UM", max_length=200)
    price = MoneyField(
        "PRICE",
        max_digits=14,
        decimal_places=2,
        default_currency="USD",
        null=True,
        blank=True,
    )
    total_cost = MoneyField(
        "TOTAL COST", max_digits=14, decimal_places=2, default_currency="USD"
    )
    expr1010 = models.CharField("Expr1010", max_length=200)
    po_no = models.CharField("PO_NO", max_length=200)
    po_date = models.DateTimeField("PO_DATE")
    vend_code = models.CharField("VEND_CODE", max_length=200)
    dbo_vend_name = models.CharField("dbo_VEND.NAME", max_length=200)
    dbo_cc_name = models.CharField("dbo_CC.NAME", max_length=200)
    acct_no = models.IntegerField("ACCT_NO", default=0)
    rcv_date = models.DateTimeField("RCV_DATE", null=True, blank=True)

    def __str__(self):
        """
        Defines the string representation of the :class:`~core.models.Order` (useful in the Admin view, but also other places where the string representation should be meaningful).
        In this case, is defined as the :class:`~core.models.Item` description field.
        """
        return self.item.descr


class ItemTransaction(models.Model):
    """
    Defines an :class:`~core.models.ItemTransaction` model representing an update to the quantity of an :class:`Item's <core.models.Item>` inventory count.
    """

    class TransactionType(models.TextChoices):
        STOCK_IN = "in"
        STOCK_OUT = "out"

    class EventType(models.TextChoices):
        STOCK_IN = "stock_in", "Stock In"
        STOCK_OUT = "stock_out", "Stock Out"
        WASTE = "waste", "Waste"
        WASTE_REVERSAL = "waste_reversal", "Waste Reversal"

    item = models.ForeignKey(
        Item, on_delete=models.PROTECT, related_name="transactions"
    )
    timestamp = models.DateTimeField(auto_now_add=True)
    occurred_at = models.DateTimeField(default=timezone.now, db_index=True)
    change = models.IntegerField()
    transaction_type = models.CharField(max_length=3, choices=TransactionType.choices)
    event_type = models.CharField(
        max_length=20, choices=EventType.choices, default=EventType.STOCK_OUT, db_index=True
    )
    reason = models.TextField("notes", blank=True)
    estimated_cost = models.DecimalField(
        max_digits=14, decimal_places=2, null=True, blank=True
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="inventory_transactions",
    )
    reversal_of = models.OneToOneField(
        "self",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="reversal",
    )

    def get_transaction_type(self) -> TransactionType:
        """
        Gets the type of transaction

        Returns:
            :class:`~core.models.ItemTransaction.TransactionType`: The :class:`~core.models.ItemTransaction` corresponding to the string representation stored in `transaction_type`.
        """
        return self.TransactionType(self.transaction_type)

    def __str__(self):
        """
        Defines the string representation of the :class:`~core.models.ItemTransaction` (useful in the Admin view, but also other places where the string representation should be meaningful).
        In this case, is defined as the a string in the following format: {<transaction date> - <:class:`~core.models.Item` name> (<quantity change>)}.
        """
        return f"{self.occurred_at.date()} - {self.item.item} ({self.change})"


class DeviceThresholdTransaction(models.Model):
    """Append-only history for manual and predicted device threshold changes."""

    class Source(models.TextChoices):
        MANUAL = "manual", "Manual"
        PREDICTED = "predicted", "Predicted"

    device = models.ForeignKey(
        Device, on_delete=models.PROTECT, related_name="threshold_changes"
    )
    timestamp = models.DateTimeField(auto_now_add=True)
    previous_threshold = models.PositiveIntegerField()
    new_threshold = models.PositiveIntegerField()
    source = models.CharField(
        max_length=10, choices=Source.choices, default=Source.MANUAL
    )
    reason = models.CharField(max_length=255, blank=True)
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="device_threshold_changes",
    )

    def __str__(self):
        return (
            f"{self.timestamp.date()} - {self.device.device_identifier} threshold "
            f"changed from {self.previous_threshold} to {self.new_threshold}"
        )


class WasteReversalRequest(models.Model):
    """Tracks approval of a requested correction to a waste transaction."""

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"

    waste_transaction = models.ForeignKey(
        ItemTransaction,
        on_delete=models.PROTECT,
        related_name="reversal_requests",
    )
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="waste_reversal_requests",
    )
    requested_at = models.DateTimeField(auto_now_add=True)
    reason = models.TextField(blank=True)
    status = models.CharField(
        max_length=10, choices=Status.choices, default=Status.PENDING, db_index=True
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="reviewed_waste_reversal_requests",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["waste_transaction"],
                condition=models.Q(status="pending"),
                name="one_pending_waste_reversal_per_transaction",
            )
        ]

    def clean(self):
        if self.waste_transaction.event_type != ItemTransaction.EventType.WASTE:
            raise ValidationError("Only waste transactions can be reversed here.")
        if self.reviewed_by_id and self.reviewed_by_id == self.requested_by_id:
            raise ValidationError("A requester cannot review their own reversal request.")

    def __str__(self):
        return f"Reversal request for transaction {self.waste_transaction_id} ({self.status})"


class NotificationEvent(models.Model):
    """Global idempotency marker recording when a notification event occurred."""

    event_key = models.CharField(max_length=255, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.event_key


class Notification(models.Model):
    """A persistent in-app notification delivered to one user."""

    class Kind(models.TextChoices):
        LOW_STOCK = "low_stock", "Low Stock"
        EXPIRING_ITEM = "expiring_item", "Expiring Item"
        EXPIRED_ITEM = "expired_item", "Expired Item"
        WASTE_REVERSAL_REQUESTED = (
            "waste_reversal_requested",
            "Waste Reversal Requested",
        )
        WASTE_REVERSAL_APPROVED = (
            "waste_reversal_approved",
            "Waste Reversal Approved",
        )
        WASTE_REVERSAL_REJECTED = (
            "waste_reversal_rejected",
            "Waste Reversal Rejected",
        )

    class Severity(models.TextChoices):
        INFO = "info", "Info"
        WARNING = "warning", "Warning"
        CRITICAL = "critical", "Critical"

    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="notifications",
    )
    kind = models.CharField(max_length=40, choices=Kind.choices, db_index=True)
    severity = models.CharField(
        max_length=10, choices=Severity.choices, default=Severity.INFO
    )
    title = models.CharField(max_length=200)
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    read_at = models.DateTimeField(null=True, blank=True)
    dismissed_at = models.DateTimeField(null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="triggered_notifications",
    )
    device = models.ForeignKey(
        Device,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="notifications",
    )
    item = models.ForeignKey(
        Item,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="notifications",
    )
    waste_reversal_request = models.ForeignKey(
        WasteReversalRequest,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="notifications",
    )
    target_url = models.CharField(max_length=500, blank=True)
    event_key = models.CharField(max_length=255, db_index=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["recipient", "event_key"],
                name="one_notification_per_user_event",
            )
        ]
        indexes = [
            models.Index(
                fields=["recipient", "dismissed_at", "read_at"],
                name="notification_inbox_idx",
            )
        ]

    def __str__(self):
        return f"{self.recipient}: {self.title}"
