"""Configures models for display and define forms used in the Admin view of the `Core` app."""

import pandas as pd
from django.contrib import admin, messages
from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.urls import path, reverse

from .forms import ExcelUploadForm, UDI_Form
from .models import Item, ItemTransaction, Order, WasteReversalRequest
from .utils import dict_from_excel_row
from .gudid import get_or_create_item_from_udi
from .services import InventoryError, record_stock_in


class OrderAdmin(admin.ModelAdmin):
    def changelist_view(self, request, extra_context=None):
        """Pass import from Excel URL to template"""
        if extra_context is None:
            extra_context = {}
        extra_context["import_url"] = reverse("admin:import_excel")
        return super().changelist_view(request, extra_context=extra_context)

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "import-excel/",
                self.admin_site.admin_view(self.import_excel),
                name="import_excel",
            ),
        ]
        return custom_urls + urls

    def import_excel(self, request):
        """Defines form for uploading an Excel document containing transaction ledger data."""
        if request.method == "POST":
            form = ExcelUploadForm(request.POST, request.FILES)
            if form.is_valid():
                file = request.FILES["excel_file"]
                df = pd.read_excel(file, engine="openpyxl")
                for _, row in df.iterrows():
                    data = dict_from_excel_row(row)
                    Order.objects.create(**data)
                return HttpResponseRedirect("../")
        else:
            form = ExcelUploadForm()

        return render(
            request, "admin/import_excel.html", {"form": form, "title": "Import Excel"}
        )

    # Select fields to display on the admin panel
    list_display = ["item_no", "descr", "po_date", "rcv_date"]

    def descr(self, obj):
        return obj.item.descr

    def item_no(self, obj):
        return obj.item.item_no


class ItemAdmin(admin.ModelAdmin):
    readonly_fields = ["is_available"]

    def changelist_view(self, request, extra_context=None):
        if extra_context is None:
            extra_context = {}
        extra_context["import_url"] = reverse("admin:import_udi")
        return super().changelist_view(request, extra_context=extra_context)

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path("import-udi/", self.admin_site.admin_view(self.import_udi), name="import_udi"),
        ]
        return custom_urls + urls

    def import_udi(self, request):
        """Defines form for adding an item using a udi."""
        if request.method == "POST":
            form = UDI_Form(request.POST)
            if form.is_valid():
                udi_input = form.cleaned_data["udi_input"]
                item = get_or_create_item_from_udi(udi_input)
                if item is None:
                    self.message_user(
                        request,
                        "The item could not be resolved. Check that the UDI is valid.",
                        level=messages.ERROR,
                    )
                else:
                    try:
                        record_stock_in(item=item, actor=request.user)
                    except InventoryError as exc:
                        self.message_user(request, str(exc), level=messages.ERROR)
                return HttpResponseRedirect("../")
        else:
            form = UDI_Form()

        return render(
            request, "admin/import_udi.html", {"form": form, "title": "Import UDI"}
        )

# Register your models here.
admin.site.register(Order, OrderAdmin)
admin.site.register(Item, ItemAdmin)


@admin.register(ItemTransaction)
class ItemTransactionAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "item",
        "event_type",
        "change",
        "occurred_at",
        "created_by",
    ]
    list_filter = ["event_type", "transaction_type", "occurred_at"]
    search_fields = ["item__item_no", "item__device__device_identifier", "reason"]

    def get_readonly_fields(self, request, obj=None):
        return [field.name for field in self.model._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(WasteReversalRequest)
class WasteReversalRequestAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "waste_transaction",
        "requested_by",
        "status",
        "requested_at",
        "reviewed_by",
    ]
    list_filter = ["status", "requested_at"]

    def get_readonly_fields(self, request, obj=None):
        return [field.name for field in self.model._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
