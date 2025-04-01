from django.http import HttpResponse
from django.shortcuts import render
from django.template import loader
from .models import Item

# Create your views here.
def order_details(request, start_date, end_date):
    orders = Item.objects.filter(po_date__range=(start_date, end_date))
    template = loader.get_template("core/order_details.html")
    context = {
        "orders": orders,
    }
    return HttpResponse(template.render(context, request))
