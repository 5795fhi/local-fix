from django.urls import path

from . import views

app_name = "complaints"

urlpatterns = [
    path("", views.my_complaints, name="my_complaints"),
    path("new/", views.raise_complaint, name="raise"),
    path("manage/", views.manage_complaints, name="manage"),
    path("manage/<int:pk>/", views.resolve_complaint, name="resolve"),
]
