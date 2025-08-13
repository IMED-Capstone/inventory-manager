import datetime
import json
import zoneinfo
from urllib.parse import urlencode

from .forms import AddRemoveItemsByBarcodeForm

import openpyxl
import simplejson
from functools import reduce
from operator import or_
from dateutil.relativedelta import relativedelta
from decimal import Decimal, InvalidOperation
from django.apps import apps
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.db.models import Count, Sum, F, Q, CharField, TextField
from django.db.models.functions import TruncMonth, TruncQuarter
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse_lazy, reverse
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.utils.safestring import mark_safe
from django.views import View
from django.views.generic import ListView
from django.views.generic.base import TemplateView
from djmoney.money import Money
from openpyxl.styles import NamedStyle

from .models import Item, Order, ItemTransaction
from .utils import style_excel_sheet, trunc_datetime, absolute_add_remove_quantity


class HomePageView(TemplateView):
    template_name = "core/home.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        core_models = apps.get_app_config("core").get_models()
        core_model_counts = {}
        for model in core_models:
            core_model_counts[model.__name__] = model.objects.count()
        context["models"] = core_model_counts
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
    paginate_by = 25

    def get_queryset(self):
        # Get all orders for filtering by date range
        orders_qs = Order.objects.all()
        current_time = timezone.localtime(timezone.now())

        # Parse dates safely
        start_date_str = self.request.GET.get("start_date")
        end_date_str = self.request.GET.get("end_date")

        if not start_date_str:
            start_date = current_time - relativedelta(years=1)
        else:
            parsed = parse_date(start_date_str)
            start_date = timezone.make_aware(datetime.datetime.combine(parsed, datetime.time.min)) if parsed else current_time

        if not end_date_str:
            end_date = current_time
        else:
            parsed = parse_date(end_date_str)
            end_date = timezone.make_aware(datetime.datetime.combine(parsed, datetime.time.max)) if parsed else current_time

        self.start_date = start_date
        self.end_date = end_date

        # Filter orders by po_date range
        filtered_orders = orders_qs.filter(po_date__range=[start_date, end_date]).order_by("-po_date")
        item_ids = filtered_orders.values_list("item", flat=True).distinct()

        # Get items linked to those orders
        items_qs = Item.objects.filter(id__in=item_ids)

        # Search filters
        search_field = self.request.GET.get("search_field")
        search_term = self.request.GET.get("search_term")
        valid_fields = [field.name for field in Item._meta.fields]

        if search_term:
            if search_field in valid_fields:
                items_qs = items_qs.filter(**{f"{search_field}__icontains": search_term})
            else:
                # Search all fields if no valid search_field given
                query = reduce(or_, [Q(**{f"{f}__icontains": search_term}) for f in valid_fields], Q())
                items_qs = items_qs.filter(query)

        sort_param = self.request.GET.get("sort", "id")
        valid_sort_fields = [f.name for f in Item._meta.fields] + [f"-{f.name}" for f in Item._meta.fields]

        if sort_param not in valid_sort_fields:
            sort_param = "id"

        items_qs = items_qs.order_by(sort_param)
        self.sort_param = sort_param

        self.items_count = items_qs.count()

        return items_qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Build a query dict excluding 'page' and 'sort' (sort handled separately)
        query_dict = self.request.GET.copy()
        query_dict.pop("page", None)
        if "sort" in query_dict:
            query_dict.pop("sort")
        context["query_string"] = urlencode(query_dict)

        context["sort"] = getattr(self, "sort_param", "id")
        context["start_date"] = self.start_date.strftime("%Y-%m-%d") if hasattr(self, "start_date") else ""
        context["end_date"] = self.end_date.strftime("%Y-%m-%d") if hasattr(self, "end_date") else ""
        context["search_field"] = self.request.GET.get("search_field", "")
        context["search_term"] = self.request.GET.get("search_term", "")
        context["per_page"] = self.request.GET.get("per_page", self.paginate_by)
        context["per_page_options"] = [25, 50, 100, 200, "All"]
        context["items_count"] = getattr(self, "items_count", 0)

        all_fields = [field.name for field in Item._meta.fields]
        context["fields"] = all_fields + ["quantity"]  # add quantity explicitly if you want

        # Pass request to template for URL building convenience
        context["request"] = self.request

        if not context["items"]:
            context["message"] = "No items available yet."

        return context

    def get_paginate_by(self, queryset):
        per_page = self.request.GET.get("per_page", self.paginate_by)
        try:
            return int(per_page)
        except (ValueError, TypeError):
            if per_page == "All":
                return queryset.count() or 1
            return self.paginate_by

class ItemTransactionView(ListView):
    model = ItemTransaction
    template_name = "core/item_transactions.html"
    context_object_name = "item_transactions"
    paginate_by = 25

    def get_quarters_list(self) -> list:
        newest_item_transaction_date = ItemTransaction.objects.order_by("-timestamp").first().timestamp
        oldest_item_transaction_date = ItemTransaction.objects.order_by("timestamp").first().timestamp

        quarter_month = ((oldest_item_transaction_date.month - 1) // 3) * 3 + 1
        aligned_start = oldest_item_transaction_date.replace(month=quarter_month, day=1)

        quarter_month_end = ((newest_item_transaction_date.month - 1) // 3) * 3 + 1
        aligned_end = newest_item_transaction_date.replace(month=quarter_month_end, day=1)

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
    
    def get_end_date_for_quarter(self, start_date: datetime.datetime):
        end_date = start_date + relativedelta(months=3)
        end_date = end_date.replace(day=1) - datetime.timedelta(days=1)
        end_date = end_date.replace(hour=23, minute=59, second=59, microsecond=999999)
        return end_date
    
    def get_dates_from_request(self):
        quarter_str = self.request.GET.get("quarter")
        if quarter_str:
            start_date = timezone.make_aware(
                datetime.datetime.combine(datetime.datetime.strptime(quarter_str, "%B %Y"), datetime.time.min)
            )
            end_date = self.get_end_date_for_quarter(start_date)
        else:
            start_date_str = self.request.GET.get("start_date")
            end_date_str = self.request.GET.get("end_date")

            start_date = timezone.make_aware(datetime.datetime.combine(parse_date(start_date_str), datetime.time.min)) if start_date_str else None
            end_date = timezone.make_aware(datetime.datetime.combine(parse_date(end_date_str), datetime.time.max)) if end_date_str else None

        self.quarter_str = quarter_str

        if not start_date or not end_date:
            start_date, end_date = self.get_default_dates()

        start_date = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
        end_date = end_date.replace(hour=23, minute=59, second=59, microsecond=999999)
        
        return start_date, end_date

    def get_queryset(self, included_fields=None):
        start_date, end_date = self.get_dates_from_request()
        self.start_date = start_date
        self.end_date = end_date

        item_no = self.request.GET.getlist("category[]")
        if any(s.strip() for s in item_no):
            queryset = ItemTransaction.objects.filter(item__item_no__in=item_no)
        else:
            queryset = ItemTransaction.objects.all()

        item_transactions = queryset.filter(timestamp__range=[start_date, end_date])

        search_field = self.request.GET.get("search_field")
        search_term = self.request.GET.get("search_term")
        valid_fields = [field.name for field in ItemTransaction._meta.fields]

        if search_term:
            if search_field in valid_fields:
                item_transactions = item_transactions.filter(**{f"{search_field}__icontains": search_term})
            else:
                query = reduce(or_, [Q(**{f"{f}__icontains": search_term}) for f in valid_fields], Q())
                item_transactions = item_transactions.filter(query)

        sort_param = self.request.GET.get("sort", "id")
        valid_sort_fields = valid_fields + [f"-{f}" for f in valid_fields]
        if sort_param not in valid_sort_fields:
            sort_param = "id"

        item_transactions = item_transactions.order_by(sort_param)
        self.sort_param = sort_param

        self.items_count = item_transactions.count()

        if included_fields:
            return item_transactions.only(*included_fields)
        return item_transactions

    def get_paginate_by(self, queryset):
        per_page = self.request.GET.get("per_page", self.paginate_by)
        try:
            return int(per_page)
        except (ValueError, TypeError):
            if per_page == "All":
                return queryset.count() or 1
            return self.paginate_by

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        if not context["item_transactions"]:
            context["message"] = "No item transactions available yet."
        else:
            lower_date_bound = ItemTransaction.objects.order_by("timestamp").first().timestamp.strftime("%Y-%m-%d")
            upper_date_bound = timezone.localtime(timezone.now()).strftime("%Y-%m-%d")
            all_fields = [field.name for field in ItemTransaction._meta.fields]
            excluded_fields = []
            included_fields = [f for f in all_fields if f not in excluded_fields]

            qset = Order.objects.all().order_by("item__descr")
            all_items = {item: descr for item, descr in qset.values_list("item__item", "item__descr")}

            query_dict = self.request.GET.copy()
            query_dict.pop("page", None)
            if "sort" in query_dict:
                query_dict.pop("sort")
            context["query_string"] = urlencode(query_dict)

            context["sort"] = getattr(self, "sort_param", "id")
            context["start_date"] = self.start_date.strftime("%Y-%m-%d")
            context["end_date"] = self.end_date.strftime("%Y-%m-%d")
            context["lower_date_bound"] = lower_date_bound
            context["upper_date_bound"] = upper_date_bound
            context["search_field"] = self.request.GET.get("search_field", "")
            context["search_term"] = self.request.GET.get("search_term", "")
            context["per_page"] = self.request.GET.get("per_page", self.paginate_by)
            context["per_page_options"] = [25, 50, 100, 200, "All"]
            context["items_count"] = getattr(self, "items_count", 0)
            context["fields"] = included_fields
            context["all_items"] = all_items

        return context


class OrderDetailsView(ListView):
    model = Order
    template_name = "core/order_details.html"
    context_object_name = "orders"
    paginate_by = 25

    def get_queryset(self):
        queryset = super().get_queryset()
        current_time = timezone.localtime(timezone.now())
        start_date_str = self.request.GET.get("start_date")
        end_date_str = self.request.GET.get("end_date")

        if not start_date_str:
            start_date = current_time - relativedelta(years=1)
        else:
            start_date = timezone.make_aware(datetime.datetime.combine(parse_date(start_date_str), datetime.time.min))

        if not end_date_str:
            end_date = current_time
        else:
            end_date = timezone.make_aware(datetime.datetime.combine(parse_date(end_date_str), datetime.time.max))

        start_date = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
        end_date = end_date.replace(hour=23, minute=59, second=59, microsecond=999999)

        self.start_date = start_date
        self.end_date = end_date

        orders = queryset.filter(po_date__range=[start_date, end_date])

        search_term = self.request.GET.get("search_term")
        search_field = self.request.GET.get("search_field")

        valid_text_fields = [
            field.name for field in Order._meta.fields
            if isinstance(field, (CharField, TextField))
        ]

        money_fields = ["price", "total_cost"]

        if search_term:
            filters = Q()

            if search_field:
                if search_field in valid_text_fields:
                    filters |= Q(**{f"{search_field}__icontains": search_term})
                elif search_field in money_fields:
                    try:
                        amount = Decimal(search_term)
                        filters |= Q(**{search_field: amount})
                    except InvalidOperation:
                        return queryset.none()
            else:
                filters |= reduce(or_, [
                    Q(**{f"{field}__icontains": search_term}) for field in valid_text_fields
                ], Q())
                try:
                    amount = Decimal(search_term)
                    for money_field in money_fields:
                        filters |= Q(**{money_field: amount})
                except InvalidOperation:
                    pass

            orders = orders.filter(filters)

        sort_param = self.request.GET.get("sort", "-po_date")
        if sort_param.lstrip('-') in [field.name for field in Order._meta.fields]:
            orders = orders.order_by(sort_param)
        else:
            orders = orders.order_by("-po_date")

        return orders

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        lower_date_bound = Order.objects.order_by('po_date').first().po_date.strftime("%Y-%m-%d")
        upper_date_bound = timezone.localtime(timezone.now()).strftime('%Y-%m-%d')

        all_fields = [field.name for field in Order._meta.fields]
        excluded_fields = ["id", "price_currency", "total_cost_currency", "item_no", "dbo_vend_name", "expr1010"]
        included_fields = [f for f in all_fields if f not in excluded_fields]

        params = self.request.GET.copy()
        params.pop('page', None)
        params.pop('sort', None)
        context['query_string'] = params.urlencode()

        context.update({
            'start_date': self.start_date.strftime("%Y-%m-%d"),
            'end_date': self.end_date.strftime("%Y-%m-%d"),
            'lower_date_bound': lower_date_bound,
            'upper_date_bound': upper_date_bound,
            'fields': included_fields,
            'per_page': self.request.GET.get('per_page', self.paginate_by),
            'per_page_options': [25, 50, 100, "All"],
            'search_field': self.request.GET.get("search_field", ""),
            'orders_count': context["paginator"].count if "paginator" in context else 0,
            'sort': self.request.GET.get("sort", "-po_date"),
        })

        context["search_term"] = self.request.GET.get("search_term", "")

        return context

    def get_paginate_by(self, queryset):
        per_page = self.request.GET.get('per_page', 25)
        try:
            return int(per_page)
        except ValueError:
            if per_page == "All":
                count = queryset.count()
                return count if count > 0 else 1
            return 25

def export_to_excel(request):
    """Export selected date range transaction data to an Excel file."""
    workbook = openpyxl.Workbook()
    sheet = workbook.active

    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    sheet.title = f"{start_date}_{end_date}"[:31]  # Excel limits sheet name to 31 characters

    # Optimize related model access
    queryset = Order.objects.select_related("item").all().order_by("-po_date")

    # Filter by date range if provided
    if start_date and end_date:
        start_date_as_datetime = timezone.make_aware(datetime.datetime.combine(parse_date(start_date), datetime.time(0, 0, 0)))
        end_date_as_datetime = timezone.make_aware(datetime.datetime.combine(parse_date(end_date), datetime.time(23, 59, 59, 999999)))
        queryset = queryset.filter(po_date__range=[start_date_as_datetime, end_date_as_datetime])

    # Define fields to exclude
    excluded_fields = {"ID", "price_currency", "total_cost_currency", "par_level", "external_url", "item"}

    # Get Order and Item fields (excluding those marked)
    order_fields = [f for f in Order._meta.fields if f.verbose_name not in excluded_fields and f.name not in excluded_fields]
    item_fields = [f for f in Order._meta.get_field("item").related_model._meta.fields if f.verbose_name not in excluded_fields and f.name not in excluded_fields]

    # Build headers and add to sheet
    column_names = [field.verbose_name for field in item_fields] + [field.verbose_name for field in order_fields]
    sheet.append(column_names)

    # Optionally apply number formatting
    currency_style = NamedStyle(name="currency_style", number_format='"$"#,##0.00')

    # Populate rows
    for order in queryset:
        row = []

        for field in item_fields:
            value = getattr(order.item, field.name)
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
        queryset = Order.objects.all()
        if not queryset.exists():
            context["message"] = "No orders available yet."
        else:

            # Get the start and end dates to use for querying
            start_date, end_date = self.get_dates_from_request()
            lower_date_bound = queryset.order_by("po_date").first().po_date.strftime("%Y-%m-%d")
            upper_date_bound = datetime.datetime.now(zoneinfo.ZoneInfo("UTC")).strftime("%Y-%m-%d")

            item_no = self.request.GET.getlist("category[]")
            selected_item = None

            qset = queryset.order_by("item__descr")
            all_items = {item: descr for item, descr in qset.values_list("item__item", "item__descr")}
            
            if item_no:
                selected_item = Order.objects.filter(item__item_no__in=item_no).values_list("item__item", flat=True)

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
                base_queryset = Order.objects.filter(po_date__range=(start_date, end_date), item__item_no__in=item_no)
            
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
            top_mfrs = base_queryset.values('item__mfr').annotate(
                count=Count('item__mfr')
            ).order_by('-count')[:50]

            # Fetch top items (top 50 by count)
            top_items = base_queryset.values('item__item').annotate(
                count=Count('item__item')
            ).order_by('-count')[:50]

            # Process mfrs
            mfrs_dict = {}
            mfrs_pareto_dict = {}
            total_mfr_count = sum(m['count'] for m in top_mfrs)
            cumulative_mfr_count = 0

            for m in top_mfrs:
                mfrs_dict[m['item__mfr']] = m['count']
                cumulative_mfr_count += m['count']
                mfrs_pareto_dict[m['item__mfr']] = (cumulative_mfr_count / total_mfr_count) * 100

            # Process items
            commonly_ordered_items_dict = {}
            commonly_ordered_items_pareto_dict = {}
            total_item_count = sum(i['count'] for i in top_items)
            cumulative_item_count = 0

            for i in top_items:
                commonly_ordered_items_dict[i['item__item']] = i['count']
                cumulative_item_count += i['count']
                commonly_ordered_items_pareto_dict[i['item__item']] = (cumulative_item_count / total_item_count) * 100
            
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

class ManageInventoryView(LoginRequiredMixin, TemplateView):
    template_name = "core/manage_inventory.html"
    login_url = reverse_lazy("admin:login")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        initial_data = {}
        if self.request.method == "GET":
            if self.request.GET.get("lookup_by_id") is not None:
                item_id = self.request.GET.get("lookup_by_id")
                if Item.objects.filter(item=item_id).exists():
                    context["lookup_by_id"] = item_id
                    initial_data["barcode"] = item_id
                else:
                    base_url = reverse_lazy("admin:core_item_add")
                    query_string = urlencode({"item": item_id, "item_no": item_id})
                    add_item_url = f"{base_url}?{query_string}"
                    context["lookup_by_id"] = ""
                    messages.error(
                        self.request,
                        mark_safe(
                            f'Item with ID "{item_id}" does not exist. Click <a href="{add_item_url}">here</a> to create.'
                        )
                    )

        form = AddRemoveItemsByBarcodeForm(initial=initial_data)
        context["add_remove_items_by_barcode_form"] = form
        return context


class AddRemoveItemsByBarcodeView(LoginRequiredMixin, View):
    template_name = "core/manage_inventory.html"
    login_url = reverse_lazy("admin:login")

    def get(self, request):
        form = AddRemoveItemsByBarcodeForm(data=request.GET)

        if form.is_valid():
            cleaned_data = form.cleaned_data
        else:
            cleaned_data = {}

        context = {
            "add_remove_items_by_barcode_form": form,
            "add_remove": cleaned_data.get("add_remove"),
            "barcode": cleaned_data.get("barcode"),
            "item_quantity": cleaned_data.get("item_quantity"),
        }

        return render(request, self.template_name, context)

    def post(self, request):
        form = AddRemoveItemsByBarcodeForm(request.POST)
        if form.is_valid():
            barcode = form.cleaned_data["barcode"]
            add_remove = form.cleaned_data["add_remove"]
            item_quantity = form.cleaned_data["item_quantity"]

            print(f"Action: {add_remove}, Barcode: {barcode}, Quantity: {item_quantity}")

            # TODO:
                # item field here (item=barcode) needs to be replaced with UDI/DI equivalent once implemented rather than item ID (which might be more UIC specific)
            item = Item.objects.filter(item=barcode)[0]
            ItemTransaction.objects.create(item=item, transaction_type=add_remove, change=absolute_add_remove_quantity(item_quantity,add_remove))

            query_string = urlencode({"add_remove": add_remove, "barcode": barcode, "item_quantity": item_quantity})
            return redirect(f"{reverse('add_remove_items_by_barcode')}?{query_string}")

        return render(request, self.template_name, {
            "add_remove_items_by_barcode_form": form,
            "add_remove": request.POST.get("add_remove"),
            "barcode": request.POST.get("barcode"),
            "item_quantity": request.POST.get("item_quantity")
        })