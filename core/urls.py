"""
Defines URLs used across the Core app.

The following URL patterns are defined:

* **items/**: Displays details for items (item-details).
* **orders/**: Displays details for orders (order-details).
* **item-transactions/**: Handles item transaction details (itemtransaction-details).
* **orders/export**: Exports order data to Excel (export-orders).
* **orders_advanced/**: Advanced order details view (order-details-advanced).
* **manage_inventory/**: Manages inventory (manage_inventory).
* **manage_inventory/add_remove/**: Adds or removes items by barcode (add_remove_items_by_barcode).
* **settings**: User settings page (settings).
* **about**: About page (about).
* **profile**: User profile page (profile).
* **pagination**: Pagination settings (pagination).
* **/**: Home page (home).
* **data-browser/**: Includes URLs from the `data_browser` app.
"""

from django.urls import include, path

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
