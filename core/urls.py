from django.urls import path

from . import views

urlpatterns = [
    path("orders/dates/<str:start_date>/<str:end_date>/", views.order_details, name="order_details"),
    path("pagination", views.PaginationView.as_view(), name="pagination"),
    path("", views.HomePageView.as_view(), name="home"),
]
