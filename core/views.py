from django.contrib import messages
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.http import HttpResponse
from django.shortcuts import render
from django.template import loader
from django.views.generic.base import TemplateView
from .models import Item
import json

import datetime
from zoneinfo import ZoneInfo
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
    orders = Item.objects.filter(po_date__range=(start_date, end_date)).values()
    template = loader.get_template("core/order_details.html")
    column_names = [f.name for f in Item._meta.get_fields()]
    context = {
        "column_names": column_names,
        "orders": orders,
    }
    return HttpResponse(template.render(context, request))

def order_details_advanced(request, start_date=((datetime.datetime.today()-relativedelta(years=1)).strftime('%Y-%m-%d')), end_date=datetime.datetime.today().strftime('%Y-%m-%d')):
    orders_by_month_keys = []
    orders_by_month_values = []

    # Get passed parameters as Python datetime objects, and get number of months elapsed between the two dates
    start_date_as_datetime = datetime.datetime.strptime(start_date, '%Y-%m-%d').date()
    end_date_as_datetime = datetime.datetime.strptime(end_date, '%Y-%m-%d').date()
    num_months = relativedelta(end_date_as_datetime, start_date_as_datetime).months + (relativedelta(end_date_as_datetime, start_date_as_datetime).years) * 12  # make sure to include years in delta

    for i in range(num_months):
        start_month = datetime.datetime.now(ZoneInfo("America/Chicago"))-relativedelta(months=(5))  # remove month offset for final version, just for testing since test data ends in December 2024
        search_month = start_month-relativedelta(months=(i-1))
        monthly_amount = Item.objects.filter(po_date__month=(search_month.month)).count()
        orders_by_month_keys.append(search_month.strftime("%B %Y"))
        orders_by_month_values.append(monthly_amount)
    template = loader.get_template("core/order_details_advanced.html")
    orders_by_month_keys.reverse()
    orders_by_month_values.reverse()
    context = {
        "start_month": orders_by_month_keys[0],
        "end_month": orders_by_month_keys[-1],
        "orders_by_month_keys": json.dumps(orders_by_month_keys, ensure_ascii=False),
        "orders_by_month_values": json.dumps(orders_by_month_values, ensure_ascii=False),
    }
    return HttpResponse(template.render(context, request))