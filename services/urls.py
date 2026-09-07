from django.urls import path

from . import views

app_name = "services"

urlpatterns = [
    path("", views.category_list, name="category_list"),
    path("providers/", views.provider_directory, name="provider_directory"),
    path("providers/<int:pk>/", views.provider_detail, name="provider_detail"),
]
