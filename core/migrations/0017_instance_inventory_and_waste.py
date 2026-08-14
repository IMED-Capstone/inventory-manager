from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


def normalize_instance_inventory(apps, schema_editor):
    """Convert legacy per-item counts to one availability state per UDI."""
    Item = apps.get_model("core", "Item")
    Device = apps.get_model("core", "Device")

    Item.objects.update(is_available=False)
    Item.objects.filter(current_count__gt=0).update(is_available=True)

    for device in Device.objects.all().iterator():
        device.current_count = Item.objects.filter(
            device_id=device.pk, is_available=True
        ).count()
        device.save(update_fields=["current_count"])


def restore_legacy_item_counts(apps, schema_editor):
    Item = apps.get_model("core", "Item")
    Item.objects.update(current_count=0)
    Item.objects.filter(is_available=True).update(current_count=1)


def classify_existing_transactions(apps, schema_editor):
    ItemTransaction = apps.get_model("core", "ItemTransaction")
    for inventory_transaction in ItemTransaction.objects.all().iterator():
        inventory_transaction.event_type = (
            "stock_in"
            if inventory_transaction.transaction_type == "in"
            else "stock_out"
        )
        inventory_transaction.occurred_at = inventory_transaction.timestamp
        inventory_transaction.save(update_fields=["event_type", "occurred_at"])


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("core", "0016_device_current_count"),
    ]

    operations = [
        migrations.AddField(
            model_name="item",
            name="is_available",
            field=models.BooleanField(db_index=True, default=False),
        ),
        migrations.RunPython(
            normalize_instance_inventory,
            reverse_code=restore_legacy_item_counts,
        ),
        migrations.RemoveField(
            model_name="item",
            name="current_count",
        ),
        migrations.AlterField(
            model_name="device",
            name="device_identifier",
            field=models.CharField(max_length=200, unique=True, verbose_name="DI"),
        ),
        migrations.AlterField(
            model_name="item",
            name="item_no",
            field=models.CharField(max_length=200, unique=True, verbose_name="ITEM_NO"),
        ),
        migrations.AddField(
            model_name="itemtransaction",
            name="created_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="inventory_transactions",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="itemtransaction",
            name="estimated_cost",
            field=models.DecimalField(
                blank=True, decimal_places=2, max_digits=14, null=True
            ),
        ),
        migrations.AddField(
            model_name="itemtransaction",
            name="event_type",
            field=models.CharField(
                choices=[
                    ("stock_in", "Stock In"),
                    ("stock_out", "Stock Out"),
                    ("waste", "Waste"),
                    ("waste_reversal", "Waste Reversal"),
                ],
                db_index=True,
                default="stock_out",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="itemtransaction",
            name="occurred_at",
            field=models.DateTimeField(
                db_index=True, default=django.utils.timezone.now
            ),
        ),
        migrations.AddField(
            model_name="itemtransaction",
            name="reversal_of",
            field=models.OneToOneField(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="reversal",
                to="core.itemtransaction",
            ),
        ),
        migrations.AlterField(
            model_name="itemtransaction",
            name="reason",
            field=models.TextField(blank=True, verbose_name="notes"),
        ),
        migrations.RunPython(
            classify_existing_transactions,
            reverse_code=migrations.RunPython.noop,
        ),
        migrations.CreateModel(
            name="WasteReversalRequest",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("requested_at", models.DateTimeField(auto_now_add=True)),
                ("reason", models.TextField(blank=True)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "Pending"),
                            ("approved", "Approved"),
                            ("rejected", "Rejected"),
                        ],
                        db_index=True,
                        default="pending",
                        max_length=10,
                    ),
                ),
                ("reviewed_at", models.DateTimeField(blank=True, null=True)),
                (
                    "requested_by",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="waste_reversal_requests",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "reviewed_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="reviewed_waste_reversal_requests",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "waste_transaction",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="reversal_requests",
                        to="core.itemtransaction",
                    ),
                ),
            ],
        ),
        migrations.AddConstraint(
            model_name="wastereversalrequest",
            constraint=models.UniqueConstraint(
                condition=models.Q(status="pending"),
                fields=("waste_transaction",),
                name="one_pending_waste_reversal_per_transaction",
            ),
        ),
    ]
