from django.urls import path, include

from . import views

urlpatterns = [
    path("items/", views.ItemDetailsView.as_view(), name="item-details"),
    path("orders/", views.OrderDetailsView.as_view(), name="order-details"),
    path("item-transactions/", views.ItemTransactionView.as_view(), name="itemtransaction-details"),
    path("orders/export", views.export_to_excel, name="export-orders"),
    path("orders_advanced/", views.OrderDetailsAdvancedView.as_view(), name="order-details-advanced"),
    path("manage_inventory/", views.ManageInventoryView.as_view(), name="manage_inventory"),
    path("manage_inventory/add_remove/", views.AddRemoveItemsByBarcodeView.as_view(), name="add_remove_items_by_barcode"),
    path("settings", views.SettingsView.as_view(), name="settings"),
    path("about", views.AboutView.as_view(), name="about"),
    path("profile", views.ProfileView.as_view(), name="profile"),
    path("pagination", views.PaginationView.as_view(), name="pagination"),
    path("", views.HomePageView.as_view(), name="home"),
    path("data-browser/", include("data_browser.urls")),
]
