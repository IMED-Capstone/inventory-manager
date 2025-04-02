from django.urls import path

from . import views

urlpatterns = [
    path("orders/dates/", views.order_details, name="order_details"),
    path("orders/dates/<str:start_date>/<str:end_date>/", views.order_details, name="order_details"),
    path("orders_advanced/dates/<str:start_date>/<str:end_date>/", views.order_details_advanced, name="order_details_advanced"),
    path("orders_advanced/dates/", views.order_details_advanced, name="order_details_advanced"),
    path("pagination", views.PaginationView.as_view(), name="pagination"),
    path("", views.HomePageView.as_view(), name="home"),
]
