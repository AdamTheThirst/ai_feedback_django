"""Маршруты технических страниц приложения ``core``."""

from django.urls import path

from apps.core.views import healthcheck_view

urlpatterns = [
    path("health/", healthcheck_view, name="healthcheck"),
]
