"""Defines models used across the Core app."""

from django.db import models
from djmoney.models.fields import MoneyField


class Item(models.Model):
    """Defines an :class:`~core.models.Item` model representing an individual item in inventory."""

    item = models.CharField("ITEM", max_length=200)
    item_no = models.CharField("ITEM_NO", max_length=200)
    mfr = models.CharField("MFR", max_length=200)
    mfr_cat = models.CharField("MFR CAT", max_length=200)
    descr = models.CharField("DESCR", max_length=200)
    par_level = models.PositiveIntegerField(blank=True, default=1)
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
        return self.transactions.aggregate(total=models.Sum("change"))["total"] or 0

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
    TODO: support recording the user submitting the transaction
    """

    class TransactionType(models.TextChoices):
        STOCK_IN = "in"
        STOCK_OUT = "out"

    item = models.ForeignKey(
        Item, on_delete=models.PROTECT, related_name="transactions"
    )
    timestamp = models.DateTimeField(auto_now_add=True)
    change = models.IntegerField()
    transaction_type = models.CharField(max_length=3, choices=TransactionType.choices)
    reason = models.CharField(max_length=255, blank=True)
    # changed_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL)        # update to include the corresponding User to submitted the transaction (should probably make custom User model first)

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
        return f"{self.timestamp.date()} - {self.item.name} ({self.change})"


class ParLevelTransaction(models.Model):
    """
    Defines a :class:`~core.models.ParLevelTransaction` model used for updating the par level of an :class:`~core.models.Item`.
    TODO: implement this in the backend
    """

    item = models.ForeignKey(Item, on_delete=models.PROTECT, related_name="par_changes")
    timestamp = models.DateTimeField(auto_now_add=True)
    previous_par = models.PositiveIntegerField()
    new_par = models.PositiveIntegerField()
    reason = models.CharField(max_length=255, blank=True)

    # changed_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL)        # update to include the corresponding User to submitted the transaction (should probably make custom User model first)
    def __str__(self):
        return f"{self.timestamp.date()} - {self.item.name} par level changed from {self.previous_par} to {self.new_par}"
