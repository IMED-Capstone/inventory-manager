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
        
        # if start_date:
        #     queryset = queryset.filter(po_date__gte=parse_date(start_date)).order_by("id")
        # if end_date:
        #     queryset = queryset.filter(po_date__lte=parse_date(end_date)).order_by("id")

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

    sheet.title = f"Orders range{start_date} - {end_date}"

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
    response['Content-Disposition'] = f'attachment; filename={sheet.title}.xlsx'
    workbook.save(response)
    return response



def order_details_advanced(request, start_date=((datetime.datetime.today()-relativedelta(years=1)).strftime('%Y-%m-%d')), end_date=datetime.datetime.today().strftime('%Y-%m-%d')):
    orders_by_month_keys = []
    orders_by_month_values = []
    cost_by_month_values = []

    # Get passed parameters as Python datetime objects, and get number of months elapsed between the two dates
    start_date_as_datetime = datetime.datetime.strptime(start_date, '%Y-%m-%d').date()
    end_date_as_datetime = datetime.datetime.strptime(end_date, '%Y-%m-%d').date()
    lower_date_bound = Item.objects.order_by('po_date').first().po_date.strftime("%Y-%m-%d")
    upper_date_bound = end_date

    initial_data = {}
    initial_data['start_date'] = start_date
    initial_data['end_date'] = end_date

    form = DateRangeForm(initial=initial_data, lower_bound=lower_date_bound, upper_bound=upper_date_bound)

    if request.method == "POST":
        form = DateRangeForm(request.POST)
        if form.is_valid():
            start_date_as_datetime = form.cleaned_data['start_date']
            end_date_as_datetime = form.cleaned_data['end_date']
            start_date = start_date_as_datetime.strftime("%Y-%m-%d")
            end_date = end_date_as_datetime.strftime("%Y-%m-%d")
    
    num_months = (relativedelta(end_date_as_datetime, start_date_as_datetime).months + (relativedelta(end_date_as_datetime, start_date_as_datetime).years) * 12) + 1  # make sure to include years in delta

    # Get monthly stats
    for i in range(num_months):
        search_month = start_date_as_datetime+relativedelta(months=i)
        monthly_amount = 0
        monthly_cost = 0

        if i == 0:  # if first month, only include values from that day of the month through the end of the month (e.g. if April 5th, don't include values from 4/1 - 4/4)
            next_month = search_month + relativedelta(months=1)
            last_day_of_month = (next_month.replace(day=1) - relativedelta(days=1)).day
            start_date = search_month
            end_date = search_month.replace(day=last_day_of_month)
            monthly_amount = Item.objects.filter(po_date__range=(start_date, end_date)).count()
            monthly_cost = Item.objects.filter(po_date__range=(start_date, end_date)).aggregate(Sum('total_cost'))['total_cost__sum']
        elif i == num_months - 1:
            start_date = search_month.replace(day=1)
            end_date = search_month
            monthly_amount = Item.objects.filter(po_date__range=(start_date, end_date)).count()
            monthly_cost = Item.objects.filter(po_date__range=(start_date, end_date)).aggregate(Sum('total_cost'))['total_cost__sum']
        else:
            monthly_amount = Item.objects.filter(po_date__year=(search_month.year), po_date__month=(search_month.month)).count()
            monthly_cost = Item.objects.filter(po_date__year=(search_month.year), po_date__month=(search_month.month)).aggregate(Sum('total_cost'))['total_cost__sum']
        orders_by_month_keys.append(search_month.strftime("%B %Y"))
        orders_by_month_values.append(monthly_amount)
        cost_by_month_values.append(monthly_cost)

    # Get mfr stats
    mfrs = Item.objects.filter(po_date__range=(start_date_as_datetime, end_date_as_datetime)).values('mfr').annotate(count=Count('mfr')).order_by("-count")
    mfrs_dict = {mfr['mfr']: mfr['count'] for mfr in mfrs}
    mfrs_keys = list(dict(mfrs_dict).keys())
    mfrs_values = list(dict(mfrs_dict).values())

    template = loader.get_template("core/order_details_advanced.html")
    context = {
        "form": form,
        "start_date": start_date,
        "end_date": end_date,
        "lower_date_bound": lower_date_bound,
        "upper_date_bound": upper_date_bound,
        "orders_by_month_keys": json.dumps(orders_by_month_keys, ensure_ascii=False),
        "orders_by_month_values": json.dumps(orders_by_month_values, ensure_ascii=False),
        "total_orders_across_range": sum(orders_by_month_values),   # if 0, no values in range, so report on client
        "cost_by_month_values": simplejson.dumps(cost_by_month_values, ensure_ascii=False, use_decimal=True),
        "mfrs_keys": json.dumps(mfrs_keys, ensure_ascii=False).replace("'", "\\'"),
        "mfrs_values": json.dumps(mfrs_values, ensure_ascii=False),
    }
    return HttpResponse(template.render(context, request))