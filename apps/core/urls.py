"""Маршруты корневого входа, главной страницы и технических endpoint-ов."""

from django.urls import path

from apps.core.views import (
    healthcheck_view,
    home_view,
    knowledge_base_placeholder_view,
    profile_placeholder_view,
    root_entry_view,
)

app_name = "core"

urlpatterns = [
    path("", root_entry_view, name="root"),
    path("home/", home_view, name="home"),
    path("profile/", profile_placeholder_view, name="profile_placeholder"),
    path("knowledge-base/", knowledge_base_placeholder_view, name="knowledge_base_placeholder"),
    path("health/", healthcheck_view, name="healthcheck"),
]
