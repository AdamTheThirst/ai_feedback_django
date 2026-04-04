"""Маршруты аутентификации и восстановления пароля."""

from django.urls import path

from apps.accounts.views import (
    LoginView,
    LogoutView,
    ProjectPasswordResetCompleteView,
    ProjectPasswordResetConfirmView,
    ProjectPasswordResetDoneView,
    ProjectPasswordResetView,
    RegisterView,
)

app_name = "accounts"

urlpatterns = [
    path("register/", RegisterView.as_view(), name="register"),
    path("login/", LoginView.as_view(), name="login"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("password-reset/", ProjectPasswordResetView.as_view(), name="password_reset"),
    path(
        "password-reset/done/",
        ProjectPasswordResetDoneView.as_view(),
        name="password_reset_done",
    ),
    path(
        "password-reset/confirm/<uidb64>/<token>/",
        ProjectPasswordResetConfirmView.as_view(),
        name="password_reset_confirm",
    ),
    path(
        "password-reset/complete/",
        ProjectPasswordResetCompleteView.as_view(),
        name="password_reset_complete",
    ),
]
