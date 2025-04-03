import pandas as pd
from django.contrib import admin
from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.urls import path, reverse

from .forms import ExcelUploadForm
from .models import Item


class ItemAdmin(admin.ModelAdmin):
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
                    Item.objects.create(
                        item=row["ITEM"],
                        mfr=row["MFR"],
                        mfr_cat=row["MFR CAT"],
                        vendor=row["VENDOR"],
                        vend_cat=row["VEND CAT"],
                        descr=row["DESCR"],
                        recv_qty=row["RECV QTY"],
                        um=row["UM"],
                        price=row["PRICE"],
                        total_cost=row["TOTAL COST"],
                        expr1010=row["Expr1010"],
                        po_no=row["PO_NO"],
                        po_date=row["PO_DATE"].tz_localize(tz="America/Chicago").tz_convert("UTC"),
                        vend_code=row["VEND_CODE"],
                        item_no=row["ITEM_NO"],
                        dbo_vend_name=row["dbo_VEND.NAME"],
                        expr1016=row["Expr1016"],
                        expr1017=row["Expr1017"]
                    )
                return HttpResponseRedirect("../")
        else:
            form = ExcelUploadForm()
        

        return render(request, "admin/import_excel.html", {"form": form, "title": "Import Excel"})

# Register your models here.
admin.site.register(Item, ItemAdmin)