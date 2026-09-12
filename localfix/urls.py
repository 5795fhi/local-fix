from django.contrib import admin
from django.urls import include, path

from core import views as core_views

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("core.urls")),
    path("accounts/", include("accounts.urls")),
    path("services/", include("services.urls")),
    path("bookings/", include("bookings.urls")),
    path("payments/", include("payments.urls")),
    path("reviews/", include("reviews.urls")),
    path("complaints/", include("complaints.urls")),
    path("notifications/", include("notifications.urls")),
    path("assistant/", include("assistant.urls")),
]

handler404 = "core.views.page_not_found"
handler500 = "core.views.server_error"
