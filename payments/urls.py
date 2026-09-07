from django.urls import path

from . import views

app_name = "payments"

urlpatterns = [
    path("<int:booking_id>/checkout/", views.checkout, name="checkout"),
    path("<int:booking_id>/pay/", views.pay, name="pay"),
    path("<int:booking_id>/receipt/", views.receipt, name="receipt"),
]
