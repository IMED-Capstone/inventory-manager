import datetime
import json
import zoneinfo

from .utils import trunc_datetime

import openpyxl
import openpyxl.utils
import simplejson
from dateutil.relativedelta import relativedelta
from django.contrib import messages
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.db.models import Count, Sum
from django.db.models.functions import TruncMonth, TruncQuarter
from django.http import HttpResponse
from django.shortcuts import redirect
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.views.generic import ListView
from django.views.generic.base import TemplateView
from djmoney.models.fields import MoneyFieldProxy
from djmoney.money import Money
from openpyxl.styles import Alignment, Border, Font, NamedStyle, PatternFill, Side

from .models import Item
from urllib.parse import urlencode


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
    
class OrderDetailsView(ListView):
    """Provides basic table view of orders, selectable by date range."""
    model = Item
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
        lower_date_bound = Item.objects.order_by('po_date').first().po_date.strftime("%Y-%m-%d")
        upper_date_bound = (timezone.localtime(timezone.now())).strftime('%Y-%m-%d')
        all_fields = [field.name for field in Item._meta.fields]
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
                return Item.objects.order_by("po_date").count()
            else:
                return 10

def export_to_excel(request):
    """Export selected date range transaction data to an Excel file."""
    workbook = openpyxl.Workbook()
    sheet = workbook.active

    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    queryset = Item.objects.all().order_by("-po_date")

    sheet.title = f"{start_date}_{end_date}"    # can't be longer than 31 characters

    if start_date and end_date:
        start_date_as_datetime = timezone.make_aware(datetime.datetime.combine(parse_date(start_date), datetime.time(0,0,0,0)))
        end_date_as_datetime = timezone.make_aware(datetime.datetime.combine(parse_date(end_date), datetime.time(23,59,59,999999)))
        queryset = queryset.filter(po_date__range=[start_date_as_datetime, end_date_as_datetime])
    
    excluded_fields = ["ID", "price_currency",  "total_cost_currency", "par_level", "external_url"]
    column_names = [field.verbose_name for field in Item._meta.fields if (field.verbose_name not in excluded_fields and field.name not in excluded_fields)]
    sheet.append(column_names)
    columns = [field.name for field in Item._meta.fields if (field.verbose_name not in excluded_fields and field.name not in excluded_fields)]

    currency_style = NamedStyle(name="currency_style", number_format='"$"#,##0.00')

    # Set appropriate timestamp
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
    
    # Apply dollar styling to money fields to match inputted Excel file.
    i = 0
    for field in Item._meta.fields:
        if (field.verbose_name not in excluded_fields and field.name not in excluded_fields):
            i += 1
            col_letter = openpyxl.utils.get_column_letter(i)
            if isinstance(getattr(Item, field.name), MoneyFieldProxy):
                for row in range(2, sheet.max_row + 1):  # Start from the second row (skip header)
                    sheet[f'{col_letter}{row}'].style = currency_style  # Apply the style to the entire column
            
            # apply header formatting
            cell_to_format = sheet.cell(row=1, column=i)
            cell_to_format.fill = PatternFill(start_color="C0C0C0", end_color="C0C0C0", fill_type="solid")
            cell_to_format.font = Font(bold=True, color="000000")
            cell_to_format.alignment = Alignment(horizontal="center", vertical="center")
            thin_border = Border(
                left=Side(style="thin", color="000000"),
                right=Side(style="thin", color="000000"),
                top=Side(style="thin", color="000000"),
                bottom=Side(style="thin", color="000000")
            )
            cell_to_format.border = thin_border


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
    """Provides graphs/visualizations of orders, selectable by date range."""
    template_name = "core/order_details_advanced.html"

    def get_quarters_list(self) -> list:
        newest_item_date = Item.objects.all().order_by("-po_date").first().po_date
        oldest_item_date = Item.objects.all().order_by("po_date").first().po_date

        quarter_month = ((oldest_item_date.month - 1) // 3) * 3 + 1
        aligned_start = oldest_item_date.replace(month=quarter_month, day=1)

        quarter_month_end = ((newest_item_date.month - 1) // 3) * 3 + 1
        aligned_end = newest_item_date.replace(month=quarter_month_end, day=1)

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
        lower_date_bound = Item.objects.order_by("po_date").first().po_date.strftime("%Y-%m-%d")
        upper_date_bound = datetime.datetime.now(zoneinfo.ZoneInfo("UTC")).strftime("%Y-%m-%d")

        item_no = self.request.GET.getlist("category[]")
        selected_item = None

        qset = Item.objects.all().order_by("descr")
        all_items = {item: descr for item, descr in qset.values_list("item", "descr")}
        
        if item_no:
            selected_item = Item.objects.filter(item__in=item_no).values_list("item", flat=True)

        start_date_str = start_date.strftime("%Y-%m-%d")
        end_date_str = end_date.strftime("%Y-%m-%d")

        delta = relativedelta(end_date, start_date)
        num_months = (delta.years * 12 + delta.months) + 1  # covers cases > 1yr (e.g. 12-month delta is 1 year and zero months)

        orders_by_month_keys = []
        orders_by_month_values = []
        cost_by_month_values = []
        orders_by_quarter_keys = []
        orders_by_quarter_values = []
        cost_by_quarter_values = []
        quarters_dict = {}

        if not selected_item:
            base_queryset = Item.objects.filter(po_date__range=(start_date, end_date))
        else:
            base_queryset = Item.objects.filter(po_date__range=(start_date, end_date), item__in=item_no)
        
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
        top_mfrs = base_queryset.values('mfr').annotate(
            count=Count('mfr')
        ).order_by('-count')[:50]

        # Fetch top items (top 50 by count)
        top_items = base_queryset.values('item').annotate(
            count=Count('item')
        ).order_by('-count')[:50]

        # Process mfrs
        mfrs_dict = {}
        mfrs_pareto_dict = {}
        total_mfr_count = sum(m['count'] for m in top_mfrs)
        cumulative_mfr_count = 0

        for m in top_mfrs:
            mfrs_dict[m['mfr']] = m['count']
            cumulative_mfr_count += m['count']
            mfrs_pareto_dict[m['mfr']] = (cumulative_mfr_count / total_mfr_count) * 100

        # Process items
        commonly_ordered_items_dict = {}
        commonly_ordered_items_pareto_dict = {}
        total_item_count = sum(i['count'] for i in top_items)
        cumulative_item_count = 0

        for i in top_items:
            commonly_ordered_items_dict[i['item']] = i['count']
            cumulative_item_count += i['count']
            commonly_ordered_items_pareto_dict[i['item']] = (cumulative_item_count / total_item_count) * 100
        
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