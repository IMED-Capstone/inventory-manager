from django.db import models
from djmoney.models.fields import MoneyField


class Item(models.Model):
    item=models.CharField('ITEM', max_length=200)
    item_no=models.CharField('ITEM_NO', max_length=200)
    mfr=models.CharField('MFR', max_length=200)
    mfr_cat=models.CharField('MFR CAT', max_length=200)
    descr=models.CharField('DESCR', max_length=200)
    par_level=models.PositiveIntegerField(blank=True, default=1)
    external_url=models.URLField(max_length=200, default="https://accessgudid.nlm.nih.gov/resources/developers/v3/device_lookup_api")

    def __str__(self):
        return self.item

# Create your models here.
class Order(models.Model):
    """Defines an Order model representing an order for an item in inventory.
    """
    item = models.ForeignKey(Item, on_delete=models.PROTECT)
    vendor=models.CharField('VENDOR', max_length=200)
    vend_cat=models.CharField('VEND CAT', max_length=200)
    recv_qty=models.IntegerField('RECV QTY')
    um=models.CharField('UM', max_length=200)
    price=MoneyField('PRICE', max_digits=14, decimal_places=2, default_currency="USD", null=True, blank=True)
    total_cost=MoneyField('TOTAL COST', max_digits=14, decimal_places=2, default_currency="USD")
    expr1010=models.CharField('Expr1010', max_length=200)
    po_no=models.CharField('PO_NO', max_length=200)
    po_date=models.DateTimeField('PO_DATE')
    vend_code=models.CharField('VEND_CODE', max_length=200)
    dbo_vend_name=models.CharField('dbo_VEND.NAME', max_length=200)
    dbo_cc_name=models.CharField('dbo_CC.NAME', max_length=200)
    acct_no=models.IntegerField('ACCT_NO', default=0)
    rcv_date=models.DateTimeField('RCV_DATE', null=True, blank=True)

    # show model description when using string representation (e.g. for display on admin panel)
    def __str__(self):
        return self.item.descr
    