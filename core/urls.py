from django.urls import path

from . import views

urlpatterns = [
    path("orders/dates/<str:start_date>/<str:end_date>/", views.order_details, name="order_details")
]
