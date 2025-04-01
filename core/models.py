from django.db import models

# Create your models here.
class Item(models.Model):
    item=models.CharField(max_length=200)
    mfr=models.CharField(max_length=200)
    mfr_cat=models.CharField(max_length=200)
    vendor=models.CharField(max_length=200)
    vend_cat=models.CharField(max_length=200)
    descr=models.CharField(max_length=200)
    recv_qty=models.IntegerField()
    um=models.CharField(max_length=200)
    price=models.FloatField(null=True, blank=True)
    total_cost=models.FloatField()
    expr1010=models.CharField(max_length=200)
    po_no=models.CharField(max_length=200)
    po_date=models.DateTimeField()
    vend_code=models.CharField(max_length=200)
    item_no=models.CharField(max_length=200)
    dbo_vend_name=models.CharField(max_length=200)
    expr1016=models.CharField(max_length=200)
    expr1017=models.IntegerField()