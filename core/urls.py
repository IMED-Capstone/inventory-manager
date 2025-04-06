from django.urls import path

from . import views

urlpatterns = [
    path("orders/", views.OrderDetailsView.as_view(), name="order_details"),
    path("orders/export", views.export_to_excel, name="export-orders"),
    path("orders_advanced/", views.OrderDetailsAdvancedView.as_view(), name="order_details_advanced"),
    path("pagination", views.PaginationView.as_view(), name="pagination"),
    path("", views.HomePageView.as_view(), name="home"),
]
