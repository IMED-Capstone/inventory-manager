import pandas as pd
from django.contrib import admin
from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.urls import path, reverse

from .forms import ExcelUploadForm
from .models import Order, Item
from .utils import dict_from_excel_row


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
            path("import-excel/", self.admin_site.admin_view(self.import_excel), name="import_excel"),
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
        

        return render(request, "admin/import_excel.html", {"form": form, "title": "Import Excel"})
    
    # Select fields to display on the admin panel
    list_display = ['descr', 'po_date', 'rcv_date']

    def descr(self, obj):
        return obj.order_item.descr

class ItemAdmin(admin.ModelAdmin):
    list_display = ['item', 'mfr', 'descr', 'par_level']

# Register your models here.
admin.site.register(Order, OrderAdmin)
admin.site.register(Item, ItemAdmin)