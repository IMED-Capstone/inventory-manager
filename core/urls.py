"""
Defines URLs used across the Core app.

The following URL patterns are defined:

* **items/**: Displays details for :class:`Items <core.models.Item>` (item-details).
* **orders/**: Displays details for :class:`Orders <core.models.Order>` (order-details).
* **item-transactions/**: Handles :class:`~core.models.ItemTransaction` details (itemtransaction-details).
* **orders/export**: Exports :class:`~core.models.Order` data to Excel (export-orders).
* **orders-advanced/**: Advanced :class:`~core.models.Order` details view (order-details-advanced).
* **manage-inventory/**: Manages inventory (manage-inventory).
* **manage-inventory/add-remove/**: Adds or removes :class:`Items <core.models.Item>` by barcode (add_remove_items_by_barcode).
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
    path("devices/", views.DeviceDetailsView.as_view(), name="device-details"),
    path(
        "devices/<int:device_id>/threshold/",
        views.UpdateDeviceThresholdView.as_view(),
        name="update-device-threshold",
    ),
    path("items/", views.ItemDetailsView.as_view(), name="item-details"),
    path("orders/", views.OrderDetailsView.as_view(), name="order-details"),
    path("item-transactions/", views.ItemTransactionView.as_view(), name="itemtransaction-details"),
    path("orders/export", views.export_to_excel, name="export-orders"),
    path("orders-advanced/", views.OrderDetailsAdvancedView.as_view(), name="order-details-advanced"),
    path("manage-inventory/", views.ManageInventoryView.as_view(), name="manage-inventory"),
    path("manage-inventory/add-remove/", views.AddRemoveItemsByBarcodeView.as_view(), name="add_remove_items_by_barcode"),
    path("waste-log/", views.WasteLogView.as_view(), name="waste-log"),
    path("notifications/", views.NotificationListView.as_view(), name="notifications"),
    path(
        "notifications/<int:notification_id>/read/",
        views.MarkNotificationReadView.as_view(),
        name="mark-notification-read",
    ),
    path(
        "notifications/<int:notification_id>/dismiss/",
        views.DismissNotificationView.as_view(),
        name="dismiss-notification",
    ),
    path(
        "notifications/clear/",
        views.ClearNotificationsView.as_view(),
        name="clear-notifications",
    ),
    path(
        "waste-log/<int:transaction_id>/request-reversal/",
        views.RequestWasteReversalView.as_view(),
        name="request-waste-reversal",
    ),
    path(
        "waste-reversal-requests/<int:request_id>/<str:action>/",
        views.ReviewWasteReversalView.as_view(),
        name="review-waste-reversal",
    ),
    path("settings", views.SettingsView.as_view(), name="settings"),
    path("about", views.AboutView.as_view(), name="about"),
    path("profile", views.ProfileView.as_view(), name="profile"),
    path("pagination", views.PaginationView.as_view(), name="pagination"),
    path("", views.HomePageView.as_view(), name="home"),
    path("data-browser/", include("data_browser.urls")),
]
