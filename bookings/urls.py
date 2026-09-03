from django.urls import path

from . import views

app_name = "bookings"

urlpatterns = [
    path("", views.booking_list, name="list"),
    path("new/<int:provider_id>/", views.create_booking, name="create"),
    path("<int:pk>/", views.booking_detail, name="detail"),
    path("<int:pk>/accept/", views.accept_booking, name="accept"),
    path("<int:pk>/reject/", views.reject_booking, name="reject"),
    path("<int:pk>/start/", views.start_booking, name="start"),
    path("<int:pk>/complete/", views.complete_booking, name="complete"),
    path("<int:pk>/cancel/", views.cancel_booking, name="cancel"),
]
