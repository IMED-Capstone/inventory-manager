import datetime
import json
import zoneinfo
from urllib.parse import urlencode

import openpyxl
import simplejson
from dateutil.relativedelta import relativedelta
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.db.models import Count, Sum
from django.db.models.functions import TruncMonth, TruncQuarter
from django.http import HttpResponse
from django.shortcuts import redirect
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.views.generic import ListView
from django.views.generic.base import TemplateView
from djmoney.money import Money
from openpyxl.styles import NamedStyle

from .models import Item, Order
from .utils import style_excel_sheet, trunc_datetime


class HomePageView(TemplateView):
    template_name = "core/home.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
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

class ItemDetailsView(ListView):
    model = Item
    template_name = "core/item_details.html"
    context_object_name = "items"
    paginate_by = 10

    def get_queryset(self, included_fields=None):
        queryset = Order.objects.all()
        start_date_str = self.request.GET.get("start_date")
        end_date_str = self.request.GET.get("end_date")

        current_time = timezone.localtime(timezone.now())

        if not start_date_str:
            start_date = (current_time - relativedelta(years=1))
            start_date_str = start_date.strftime("%Y-%m-%d")
        else:
            start_date = timezone.make_aware(datetime.datetime.combine(parse_date(start_date_str), datetime.time(0,0,0,0)))
        if not end_date_str:
            end_date = current_time
            end_date_str = end_date.strftime("%Y-%m-%d")
        else:
            end_date = timezone.make_aware(datetime.datetime.combine(parse_date(end_date_str), datetime.time(23,59,59,999999)))
        
        # To include all items based on the date, start date should start at 12 AM and end date should end at 11:59 PM
        start_date = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
        end_date = end_date.replace(hour=23, minute=59, second=59, microsecond=999999)

        self.start_date = start_date
        self.end_date = end_date

        orders = queryset.filter(po_date__range=[start_date, end_date]).order_by("-po_date")

        item_ids = orders.values_list("order_item", flat=True).distinct()
        
        
        if not included_fields:
            return Item.objects.filter(id__in=item_ids)
        else:
            return Item.objects.filter(id__in=item_ids).only(*included_fields)
        
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        lower_date_bound = Order.objects.order_by('po_date').first().po_date.strftime("%Y-%m-%d")
        upper_date_bound = (timezone.localtime(timezone.now())).strftime('%Y-%m-%d')
        all_fields = [field.name for field in Item._meta.fields]
        excluded_fields = []
        included_fields = [field for field in all_fields if field not in excluded_fields]
        context['start_date'] = self.start_date.strftime("%Y-%m-%d")
        context['end_date'] = self.end_date.strftime("%Y-%m-%d")
        context['lower_date_bound'] = lower_date_bound
        context['upper_date_bound'] = upper_date_bound
        context["fields"] = included_fields
        context['per_page'] = self.request.GET.get('per_page', self.paginate_by)
        context['per_page_options'] = [5, 10, 25, 50, 100, "All"]
        context['items_count'] = self.get_queryset(included_fields).count()
        return context

    def get_paginate_by(self, queryset):
        per_page = self.request.GET.get('per_page', 10)
        try:
            return int(per_page)
        except ValueError:
            if per_page == "All":
                return Item.objects.order_by("item").count()
            else:
                return 10

class OrderDetailsView(ListView):
    """Provides basic table view of orders, selectable by date range."""
    model = Order
    template_name = "core/order_details.html"
    context_object_name = "orders"
    paginate_by = 10

    def get_queryset(self, included_fields=None):
        queryset = super().get_queryset()
        start_date_str = self.request.GET.get("start_date")
        end_date_str = self.request.GET.get("end_date")

        current_time = timezone.localtime(timezone.now())

        if not start_date_str:
            start_date = (current_time - relativedelta(years=1))
            start_date_str = start_date.strftime("%Y-%m-%d")
        else:
            start_date = timezone.make_aware(datetime.datetime.combine(parse_date(start_date_str), datetime.time(0,0,0,0)))
        if not end_date_str:
            end_date = current_time
            end_date_str = end_date.strftime("%Y-%m-%d")
        else:
            end_date = timezone.make_aware(datetime.datetime.combine(parse_date(end_date_str), datetime.time(23,59,59,999999)))
        
        # To include all orders based on the date, start date should start at 12 AM and end date should end at 11:59 PM
        start_date = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
        end_date = end_date.replace(hour=23, minute=59, second=59, microsecond=999999)

        self.start_date = start_date
        self.end_date = end_date
        
        if not included_fields:
            return queryset.filter(po_date__range=[start_date, end_date]).order_by("-po_date")
        else:
            return queryset.filter(po_date__range=[start_date, end_date]).only(*included_fields).order_by("-po_date")
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        lower_date_bound = Order.objects.order_by('po_date').first().po_date.strftime("%Y-%m-%d")
        upper_date_bound = (timezone.localtime(timezone.now())).strftime('%Y-%m-%d')
        all_fields = [field.name for field in Order._meta.fields]
        excluded_fields = ["id", "price_currency", "total_cost_currency", "item_no", "dbo_vend_name", "expr1010"]
        included_fields = [field for field in all_fields if field not in excluded_fields]
        context['start_date'] = self.start_date.strftime("%Y-%m-%d")
        context['end_date'] = self.end_date.strftime("%Y-%m-%d")
        context['lower_date_bound'] = lower_date_bound
        context['upper_date_bound'] = upper_date_bound
        context["fields"] = included_fields
        context['per_page'] = self.request.GET.get('per_page', self.paginate_by)
        context['per_page_options'] = [5, 10, 25, 50, 100, "All"]
        context['orders_count'] = self.get_queryset(included_fields).count()
        return context
    
    def get_paginate_by(self, queryset):
        per_page = self.request.GET.get('per_page', 10)
        try:
            return int(per_page)
        except ValueError:
            if per_page == "All":
                return Order.objects.order_by("po_date").count()
            else:
                return 10

def export_to_excel(request):
    """Export selected date range transaction data to an Excel file."""
    workbook = openpyxl.Workbook()
    sheet = workbook.active

    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    sheet.title = f"{start_date}_{end_date}"[:31]  # Excel limits sheet name to 31 characters

    # Optimize related model access
    queryset = Order.objects.select_related("order_item").all().order_by("-po_date")

    # Filter by date range if provided
    if start_date and end_date:
        start_date_as_datetime = timezone.make_aware(datetime.datetime.combine(parse_date(start_date), datetime.time(0, 0, 0)))
        end_date_as_datetime = timezone.make_aware(datetime.datetime.combine(parse_date(end_date), datetime.time(23, 59, 59, 999999)))
        queryset = queryset.filter(po_date__range=[start_date_as_datetime, end_date_as_datetime])

    # Define fields to exclude
    excluded_fields = {"ID", "price_currency", "total_cost_currency", "par_level", "external_url", "order_item"}

    # Get Order and Item fields (excluding those marked)
    order_fields = [f for f in Order._meta.fields if f.verbose_name not in excluded_fields and f.name not in excluded_fields]
    item_fields = [f for f in Order._meta.get_field("order_item").related_model._meta.fields if f.verbose_name not in excluded_fields and f.name not in excluded_fields]

    # Build headers and add to sheet
    column_names = [field.verbose_name for field in item_fields] + [field.verbose_name for field in order_fields]
    sheet.append(column_names)

    # Optionally apply number formatting
    currency_style = NamedStyle(name="currency_style", number_format='"$"#,##0.00')

    # Populate rows
    for order in queryset:
        row = []

        for field in item_fields:
            value = getattr(order.order_item, field.name)
            if isinstance(value, Money):
                row.append(value.amount)
            elif isinstance(value, datetime.datetime):
                row.append(value.astimezone(zoneinfo.ZoneInfo("America/Chicago")).strftime("%d/%m/%Y %I:%M:%S %p"))
            else:
                row.append(value)

        for field in order_fields:
            value = getattr(order, field.name)
            if isinstance(value, Money):
                row.append(value.amount)
            elif isinstance(value, datetime.datetime):
                row.append(value.astimezone(zoneinfo.ZoneInfo("America/Chicago")).strftime("%d/%m/%Y %I:%M:%S %p"))
            else:
                row.append(value)

        sheet.append(row)
    
    # Apply dollar styling to money fields to match inputted Excel file.
    i = 0
    for field in (Item._meta.fields):
        if (field.verbose_name not in excluded_fields and field.name not in excluded_fields):
            i += 1
            style_excel_sheet(sheet, Item, field, i, currency_style)
    for field in (Order._meta.fields):
        if (field.verbose_name not in excluded_fields and field.name not in excluded_fields):
            i += 1
            style_excel_sheet(sheet, Order, field, i, currency_style)
    
    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = f'attachment; filename=Orders_{sheet.title}.xlsx'
    workbook.save(response)
    return response


class OrderDetailsAdvancedView(TemplateView):
    """Provides graphs/visualizations of orders, selectable by date range."""
    template_name = "core/order_details_advanced.html"

    def get_quarters_list(self) -> list:
        newest_order_date = Order.objects.all().order_by("-po_date").first().po_date
        oldest_order_date = Order.objects.all().order_by("po_date").first().po_date

        quarter_month = ((oldest_order_date.month - 1) // 3) * 3 + 1
        aligned_start = oldest_order_date.replace(month=quarter_month, day=1)

        quarter_month_end = ((newest_order_date.month - 1) // 3) * 3 + 1
        aligned_end = newest_order_date.replace(month=quarter_month_end, day=1)

        delta = relativedelta(aligned_end, aligned_start)
        months_diff = delta.years * 12 + delta.months

        return [
            (aligned_start + relativedelta(months=i)).strftime("%B %Y")
            for i in range(0, months_diff + 1, 3)
        ]

    def get_default_dates(self):
        end_date = timezone.localtime(timezone.now())
        start_date = end_date - relativedelta(years=1)
        return start_date, end_date
    
    def get_end_date_for_quarter(self, start_date:datetime.datetime):
        end_date = start_date + relativedelta(months=3)
        end_date = end_date.replace(day=1) - datetime.timedelta(days=1)
        end_date = end_date.replace(hour=23, minute=59, second=59, microsecond=999999)
        return end_date

    def get_dates_from_request(self):
        quarter_str = self.request.GET.get("quarter")
        if quarter_str:
            start_date = timezone.make_aware(datetime.datetime.combine(datetime.datetime.strptime(quarter_str, "%B %Y"), datetime.time(0,0,0,0)))
            end_date = self.get_end_date_for_quarter(start_date)
        else:
            start_date_str = self.request.GET.get("start_date")
            end_date_str = self.request.GET.get("end_date")

            start_date = timezone.make_aware(datetime.datetime.combine(parse_date(start_date_str), datetime.time(0,0,0,0))) if start_date_str else None
            end_date = timezone.make_aware(datetime.datetime.combine(parse_date(end_date_str), datetime.time(23,59,59,999999))) if end_date_str else None

        self.quarter_str = self.request.GET.get("quarter")

        if not start_date or not end_date:
            start_date, end_date = self.get_default_dates()

        start_date = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
        end_date = end_date.replace(hour=23, minute=59, second=59, microsecond=999999)
        
        return start_date, end_date
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
    
        # Get the start and end dates to use for querying
        start_date, end_date = self.get_dates_from_request()
        lower_date_bound = Order.objects.order_by("po_date").first().po_date.strftime("%Y-%m-%d")
        upper_date_bound = datetime.datetime.now(zoneinfo.ZoneInfo("UTC")).strftime("%Y-%m-%d")

        item_no = self.request.GET.getlist("category[]")
        selected_item = None

        qset = Order.objects.all().order_by("order_item__descr")
        all_items = {item: descr for item, descr in qset.values_list("order_item__item", "order_item__descr")}
        
        if item_no:
            selected_item = Order.objects.filter(order_item__item_no__in=item_no).values_list("order_item__item", flat=True)

        start_date_str = start_date.strftime("%Y-%m-%d")
        end_date_str = end_date.strftime("%Y-%m-%d")

        orders_by_month_keys = []
        orders_by_month_values = []
        cost_by_month_values = []
        orders_by_quarter_keys = []
        orders_by_quarter_values = []
        cost_by_quarter_values = []
        quarters_dict = {}

        if not selected_item:
            base_queryset = Order.objects.filter(po_date__range=(start_date, end_date))
        else:
            base_queryset = Order.objects.filter(po_date__range=(start_date, end_date), order_item__item_no__in=item_no)
        
        monthly_data = base_queryset.annotate(
            month=TruncMonth('po_date')
        ).values(
            "month"
        ).annotate(
            total_orders=Count("id"),
            total_cost=Sum("total_cost")
        ).order_by("month")

        quarterly_data = base_queryset.annotate(
            quarter=TruncQuarter("po_date")
        ).values(
            "quarter"
        ).annotate(
            total_orders=Count("id"),
            total_cost=Sum("total_cost")
        ).order_by("quarter")

        for entry in monthly_data:
            orders_by_month_keys.append(entry["month"].strftime("%B %Y"))
            orders_by_month_values.append(entry["total_orders"])
            cost_by_month_values.append(entry["total_cost"] or 0)
        
        for entry in quarterly_data:
            quarter_number = (entry['quarter'].month - 1) // 3 + 1
            quarter_label = f"Q{quarter_number} {entry['quarter'].year}"

            orders_by_quarter_keys.append(quarter_label)
            orders_by_quarter_values.append(entry['total_orders'])
            cost_by_quarter_values.append(entry['total_cost'] or 0)

        # Fetch top manufacturers (top 50 by count)
        top_mfrs = base_queryset.values('order_item__mfr').annotate(
            count=Count('order_item__mfr')
        ).order_by('-count')[:50]

        # Fetch top items (top 50 by count)
        top_items = base_queryset.values('order_item__item').annotate(
            count=Count('order_item__item')
        ).order_by('-count')[:50]

        # Process mfrs
        mfrs_dict = {}
        mfrs_pareto_dict = {}
        total_mfr_count = sum(m['count'] for m in top_mfrs)
        cumulative_mfr_count = 0

        for m in top_mfrs:
            mfrs_dict[m['order_item__mfr']] = m['count']
            cumulative_mfr_count += m['count']
            mfrs_pareto_dict[m['order_item__mfr']] = (cumulative_mfr_count / total_mfr_count) * 100

        # Process items
        commonly_ordered_items_dict = {}
        commonly_ordered_items_pareto_dict = {}
        total_item_count = sum(i['count'] for i in top_items)
        cumulative_item_count = 0

        for i in top_items:
            commonly_ordered_items_dict[i['order_item__item']] = i['count']
            cumulative_item_count += i['count']
            commonly_ordered_items_pareto_dict[i['order_item__item']] = (cumulative_item_count / total_item_count) * 100
        
        try:
            selected_item = list(selected_item)
            if len(selected_item == 0):
                selected_item = ""
            else:
                selected_item = json.dumps(selected_item, ensure_ascii=False)
        except TypeError:
            if not selected_item:
                selected_item = ""
        
        for quarter in self.get_quarters_list():
            quarter_date_obj = datetime.datetime.strptime(quarter, "%B %Y")
            quarter_date = (quarter_date_obj.month - 1) // 3 + 1
            quarters_dict[quarter] = f"Q{quarter_date} {quarter_date_obj.year}"

        context.update({
            "start_date": start_date_str,
            "end_date": end_date_str,
            "lower_date_bound": lower_date_bound,
            "upper_date_bound": upper_date_bound,
            "orders_by_month_keys": json.dumps(orders_by_month_keys, ensure_ascii=False),
            "orders_by_month_values": json.dumps(orders_by_month_values, ensure_ascii=False),
            "orders_by_quarter_keys": json.dumps(orders_by_quarter_keys, ensure_ascii=False),
            "orders_by_quarter_values": json.dumps(orders_by_quarter_values, ensure_ascii=False),
            "total_orders_across_range": sum(orders_by_month_values),
            "cost_by_month_values": simplejson.dumps(cost_by_month_values, ensure_ascii=False, use_decimal=True),
            "cost_by_quarter_values": simplejson.dumps(cost_by_quarter_values, ensure_ascii=False, use_decimal=True),
            "mfrs_keys": json.dumps(list(mfrs_dict.keys()), ensure_ascii=False).replace("'", "\\'"),
            "mfrs_values": json.dumps(list(mfrs_dict.values()), ensure_ascii=False),
            "mfrs_pareto": json.dumps(list(mfrs_pareto_dict.values()), ensure_ascii=False),
            "commonly_ordered_keys": json.dumps(list(commonly_ordered_items_dict.keys()), ensure_ascii=False),
            "commonly_ordered_values": json.dumps(list(commonly_ordered_items_dict.values()), ensure_ascii=False),
            "commonly_ordered_values_pareto": json.dumps(list(commonly_ordered_items_pareto_dict.values()), ensure_ascii=False),
            "selected_item_no": selected_item,
            "all_items": all_items,
            "all_quarters": quarters_dict,
            "selected_quarter": self.quarter_str,
        })
        return context

    def dispatch(self, request, *args, **kwargs):
        if request.method == "GET":
            quarter_str = self.request.GET.get("quarter")
            if quarter_str:
                start_date = timezone.make_aware(datetime.datetime.combine(datetime.datetime.strptime(quarter_str, "%B %Y"), datetime.time(0,0,0,0)))
                end_date = self.get_end_date_for_quarter(start_date)

                start_date_str = self.request.GET.get("start_date")
                end_date_str = self.request.GET.get("end_date")

                start_date_from_request = timezone.make_aware(datetime.datetime.combine(parse_date(start_date_str), datetime.time(0,0,0,0))) if start_date_str else None
                end_date_from_request = timezone.make_aware(datetime.datetime.combine(parse_date(end_date_str), datetime.time(23,59,59,999999))) if end_date_str else None

                if (trunc_datetime(start_date) != trunc_datetime(start_date_from_request)) and (trunc_datetime(end_date) != trunc_datetime(end_date_from_request)):
                    new_params = {
                        "start_date": start_date.strftime("%Y-%m-%d"),
                        "quarter": quarter_str,
                        "end_date": end_date.strftime("%Y-%m-%d"),
                    }

                    new_url = f"{request.path}?{urlencode(new_params)}"
                    return redirect(new_url)

        return super().dispatch(request, *args, **kwargs)