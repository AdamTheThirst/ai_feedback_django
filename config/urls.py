"""Корневая маршрутизация проекта для пользовательских и технических страниц."""

from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("auth/", include("apps.accounts.urls")),
    path("", include("apps.core.urls")),
]
