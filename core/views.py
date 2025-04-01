from django.contrib import messages
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.http import HttpResponse
from django.shortcuts import render
from django.template import loader
from django.views.generic.base import TemplateView
from .models import Item

import datetime
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
    orders = Item.objects.filter(po_date__range=(start_date, end_date))
    template = loader.get_template("core/order_details.html")
    context = {
        "orders": orders,
    }
    return HttpResponse(template.render(context, request))
