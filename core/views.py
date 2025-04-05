import datetime
import json
import zoneinfo

import openpyxl
import openpyxl.utils
import simplejson
from dateutil.relativedelta import relativedelta
from django.contrib import messages
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.db.models import Count, Sum
from django.http import HttpResponse
from django.template import loader
from django.utils.dateparse import parse_date
from django.views.generic import ListView
from django.views.generic.base import TemplateView
from djmoney.models.fields import MoneyFieldProxy
from djmoney.money import Money
from openpyxl.styles import NamedStyle

from .forms import DateRangeForm
from .models import Item


# Create your views here.
class HomePageView(TemplateView):
    template_name = "core/home.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        messages.info(self.request, "hello Inventory Manager")
        return context

class PaginationView(TemplateView):
    template_name = "core/pagination.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        lines = []
        for i in range(200):
            lines.append(f"Line {i + 1}")
        paginator = Paginator(lines, 10)
        page = self.request.GET.get("page")
        try:
            show_lines = paginator.page(page)
        except PageNotAnInteger:
            # If page is not an integer, deliver first page.
            show_lines = paginator.page(1)
        except EmptyPage:
            # If page is out of range (e.g. 9999), deliver last page of results.
            show_lines = paginator.page(paginator.num_pages)
        context["lines"] = show_lines
        return context
    
class OrderDetailsView(ListView):
    model = Item
    template_name = "core/order_details.html"
    context_object_name = "orders"
    paginate_by = 10

    def get_queryset(self):
        queryset = super().get_queryset()
        start_date = self.request.GET.get("start_date")
        end_date = self.request.GET.get("end_date")

        if not start_date:
            start_date = (datetime.datetime.today()-relativedelta(years=1)).strftime('%Y-%m-%d')
        if not end_date:
            end_date = datetime.datetime.today().strftime('%Y-%m-%d')

        self.start_date = start_date
        self.end_date = end_date
        
        return queryset.filter(po_date__range=[start_date, end_date])
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        lower_date_bound = Item.objects.order_by('po_date').first().po_date.strftime("%Y-%m-%d")
        upper_date_bound = datetime.datetime.today().strftime('%Y-%m-%d')
        context['start_date'] = self.start_date
        context['end_date'] = self.end_date
        context['lower_date_bound'] = lower_date_bound
        context['upper_date_bound'] = upper_date_bound
        context["fields"] = [field.name for field in Item._meta.fields]
        context['per_page'] = self.request.GET.get('per_page', self.paginate_by)
        context['per_page_options'] = [5, 10, 25, 50, 100, "All"]
        context['orders_count'] = self.get_queryset().count()
        return context
    
    def get_paginate_by(self, queryset):
        per_page = self.request.GET.get('per_page', 10)
        try:
            return int(per_page)
        except ValueError:
            if per_page == "All":
                return Item.objects.count()
            else:
                return 10

def export_to_excel(request):
    workbook = openpyxl.Workbook()
    sheet = workbook.active

    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    queryset = Item.objects.all()

    sheet.title = f"{start_date}_{end_date}"    # can't be longer than 31 characters

    if start_date:
        queryset = queryset.filter(po_date__gte=parse_date(start_date)).order_by("id")
    if end_date:
        queryset = queryset.filter(po_date__lte=parse_date(end_date)).order_by("id")
    
    excluded_fields = ["ID", "price_currency",  "total_cost_currency", "par_level"]
    column_names = [field.verbose_name for field in Item._meta.fields if (field.verbose_name not in excluded_fields and field.name not in excluded_fields)]
    sheet.append(column_names)
    columns = [field.name for field in Item._meta.fields if (field.verbose_name not in excluded_fields and field.name not in excluded_fields)]

    currency_style = NamedStyle(name="currency_style", number_format='"$"#,##0.00')

    for item in queryset:
        row = []
        for field in columns:
            value = getattr(item, field)
            if isinstance(value, Money):
                row.append(value.amount)
            elif isinstance(value, datetime.datetime):
                row.append(value.astimezone(zoneinfo.ZoneInfo("America/Chicago")).strftime("%d/%m/%Y %H:%M:%S %p"))
            else:
                row.append(value)

        sheet.append(row)
    
    i = 0
    for field in Item._meta.fields:
        if (field.verbose_name not in excluded_fields and field.name not in excluded_fields):
            i += 1
            col_letter = openpyxl.utils.get_column_letter(i)
            if isinstance(getattr(Item, field.name), MoneyFieldProxy):
                for row in range(2, sheet.max_row + 1):  # Start from the second row (skip header)
                    sheet[f'{col_letter}{row}'].style = currency_style  # Apply the style to the entire column
            max_length = 0
            for cell in list(sheet.columns)[i-1]:
                if len(str(cell.value)) > max_length:
                    max_length = len(str(cell.value))
            
            sheet.column_dimensions[col_letter].width = (max_length + 2)
    
    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = f'attachment; filename=Orders_{sheet.title}.xlsx'
    workbook.save(response)
    return response


class OrderDetailsAdvancedView(TemplateView):
    template_name = "core/order_details_advanced.html"

    def get_default_dates(self):
        end_date = datetime.datetime.today().date()
        start_date = end_date - relativedelta(years=1)
        return start_date, end_date

    def get_dates_from_request(self):
        start_date_str = self.request.GET.get("start_date")
        end_date_str = self.request.GET.get("end_date")

        start_date = parse_date(start_date_str) if start_date_str else None
        end_date = parse_date(end_date_str) if end_date_str else None

        if not start_date or not end_date:
            start_date, end_date = self.get_default_dates()
        
        return start_date, end_date
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
    
        start_date, end_date = self.get_dates_from_request()
        lower_date_bound = Item.objects.order_by("po_date").first().po_date.strftime("%Y-%m-%d")
        upper_date_bound = datetime.datetime.today().strftime("%Y-%m-%d")

        start_date_str = start_date.strftime("%Y-%m-%d")
        end_date_str = end_date.strftime("%Y-%m-%d")

        delta = relativedelta(end_date, start_date)
        num_months = (delta.years * 12 + delta.months) + 1  # covers cases > 1yr (e.g. 12-month delta is 1 year and zero months)

        orders_by_month_keys = []
        orders_by_month_values = []
        cost_by_month_values = []

        for i in range(num_months):
            search_month = start_date + relativedelta(months=i)
            if i == 0:
                next_month = search_month + relativedelta(months=1)
                last_day = (next_month.replace(day=1) - relativedelta(days=1)).day
                range_start = search_month
                range_end = search_month.replace(day=last_day)
            elif i == num_months - 1:
                range_start = search_month.replace(day=1)
                range_end = end_date
            else:
                range_start = search_month.replace(day=1)
                next_month = search_month + relativedelta(months=1)
                range_end = next_month.replace(day=1) - relativedelta(days=1)

            queryset = Item.objects.filter(po_date__range=(range_start, range_end))
            monthly_amount = queryset.count()
            monthly_cost = queryset.aggregate(Sum('total_cost'))['total_cost__sum'] or 0

            orders_by_month_keys.append(search_month.strftime("%B %Y"))
            orders_by_month_values.append(monthly_amount)
            cost_by_month_values.append(monthly_cost)

        mfrs = Item.objects.filter(po_date__range=(start_date, end_date)).values('mfr').annotate(count=Count('mfr')).order_by("-count")
        mfrs_dict = {m['mfr']: m['count'] for m in mfrs}

        context.update({
            "start_date": start_date_str,
            "end_date": end_date_str,
            "lower_date_bound": lower_date_bound,
            "upper_date_bound": upper_date_bound,
            "orders_by_month_keys": json.dumps(orders_by_month_keys, ensure_ascii=False),
            "orders_by_month_values": json.dumps(orders_by_month_values, ensure_ascii=False),
            "total_orders_across_range": sum(orders_by_month_values),
            "cost_by_month_values": simplejson.dumps(cost_by_month_values, ensure_ascii=False, use_decimal=True),
            "mfrs_keys": json.dumps(list(mfrs_dict.keys()), ensure_ascii=False).replace("'", "\\'"),
            "mfrs_values": json.dumps(list(mfrs_dict.values()), ensure_ascii=False),
        })
        return context
