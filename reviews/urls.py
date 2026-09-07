from django.urls import path

from . import views

app_name = "reviews"

urlpatterns = [
    path("<int:booking_id>/new/", views.leave_review, name="leave"),
]
