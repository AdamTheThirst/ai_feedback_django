"""Маршруты пользовательского контента: список игр и страница выбранной игры."""

from django.urls import path

from apps.content.views import game_detail_view, game_list_view

app_name = "content"

urlpatterns = [
    path("games/", game_list_view, name="game_list"),
    path("games/<slug:game_slug>/", game_detail_view, name="game_detail"),
]
