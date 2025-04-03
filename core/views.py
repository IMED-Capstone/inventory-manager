from django.contrib import messages
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.db.models import Sum, Count
from django.http import HttpResponse
from django.shortcuts import render
from django.template import loader
from django.views.generic.base import TemplateView
from django.utils.timezone import make_aware
from .models import Item
from .forms import DateRangeForm
import json
import simplejson

import datetime
from zoneinfo import ZoneInfo
import pandas as pd
from dateutil.relativedelta import relativedelta

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
    
def order_details(request, start_date=((datetime.datetime.today()-relativedelta(years=1)).strftime('%Y-%m-%d')), end_date=datetime.datetime.today().strftime('%Y-%m-%d')):
    initial_data = {}
    initial_data['start_date'] = datetime.datetime.strptime(start_date, '%Y-%m-%d').date()
    initial_data['end_date'] = datetime.datetime.strptime(end_date, '%Y-%m-%d').date()

    lower_date_bound = Item.objects.order_by('po_date').first().po_date.strftime("%Y-%m-%d")

    initial_data = {}
    initial_data['start_date'] = start_date
    initial_data['end_date'] = end_date

    form = DateRangeForm(initial=initial_data, lower_bound=lower_date_bound, upper_bound=end_date)

    if request.method == "POST":
        form = DateRangeForm(request.POST)
        if form.is_valid():
            start_date = form.cleaned_data['start_date'].strftime("%Y-%m-%d")
            end_date = form.cleaned_data['end_date'].strftime("%Y-%m-%d")

    if request.method == "POST":
        if "download_date_ranges" in request.POST:
            orders = Item.objects.filter(po_date__range=(start_date, end_date)).values()
            orders_list = list(orders)
            response = HttpResponse(content_type='application/vnd.ms-excel')
            output_name = f"{start_date}..{end_date}"
            response['Content-Disposition'] = f'attachment; filename={output_name}.xlsx'
            for order in orders_list:
                order["po_date"] = order["po_date"].strftime("%d/%m/%Y %H:%M:%S %p")
                order.pop("id")
                order.pop("par_level")
            df = pd.DataFrame(orders_list)
            writer = pd.ExcelWriter(response, engine="xlsxwriter")
            df.to_excel(writer, index=False)
            writer.close()
            return response
    
    orders = Item.objects.filter(po_date__range=(start_date, end_date)).values()

    template = loader.get_template("core/order_details.html")
    column_names = [f.name for f in Item._meta.get_fields()]
    context = {
        "form": form,
        "column_names": column_names,
        "orders": orders,
        "orders_count": orders.count()
    }
    return HttpResponse(template.render(context, request))

def order_details_advanced(request, start_date=((datetime.datetime.today()-relativedelta(years=1)).strftime('%Y-%m-%d')), end_date=datetime.datetime.today().strftime('%Y-%m-%d')):
    orders_by_month_keys = []
    orders_by_month_values = []
    cost_by_month_values = []

    # Get passed parameters as Python datetime objects, and get number of months elapsed between the two dates
    start_date_as_datetime = datetime.datetime.strptime(start_date, '%Y-%m-%d').date()
    end_date_as_datetime = datetime.datetime.strptime(end_date, '%Y-%m-%d').date()
    lower_date_bound = Item.objects.order_by('po_date').first().po_date.strftime("%Y-%m-%d")
    # upper_date_bound = Item.objects.order_by('-po_date').first().po_date.strftime("%Y-%m-%d")
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

    # Get vendor stats
    vendors = Item.objects.filter(po_date__range=(start_date_as_datetime, end_date_as_datetime)).values('vendor').annotate(count=Count('vendor')).order_by("-count")
    vendors_dict = {vendor['vendor']: vendor['count'] for vendor in vendors}
    vendors_keys = list(dict(vendors_dict).keys())
    vendors_values = list(dict(vendors_dict).values())

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
        "vendors_keys": json.dumps(vendors_keys, ensure_ascii=False).replace("'", "\\'"),
        "vendors_values": json.dumps(vendors_values, ensure_ascii=False),
    }
    return HttpResponse(template.render(context, request))