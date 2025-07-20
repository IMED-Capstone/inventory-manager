from django.urls import path

from . import views

urlpatterns = [
    path("items/", views.ItemDetailsView.as_view(), name="item_details"),
    path("orders/", views.OrderDetailsView.as_view(), name="order_details"),
    path("orders/export", views.export_to_excel, name="export-orders"),
    path("orders_advanced/", views.OrderDetailsAdvancedView.as_view(), name="order_details_advanced"),
    path("manage_inventory/", views.ManageInventoryView.as_view(), name="manage_inventory"),
    path("manage_inventory/add_remove/", views.AddRemoveItemsByBarcodeView.as_view(), name="add_remove_items_by_barcode"),
    path("pagination", views.PaginationView.as_view(), name="pagination"),
    path("", views.HomePageView.as_view(), name="home"),
]
