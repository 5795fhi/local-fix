from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("register/", views.register, name="register"),
    path("login/", views.CustomLoginView.as_view(), name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("verify/", views.verify, name="verify"),
    path("verify/resend/", views.resend_otp, name="resend_otp"),
    path("profile/", views.profile, name="profile"),
]
