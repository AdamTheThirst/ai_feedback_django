"""Корневые маршруты проекта с подключением пользовательских разделов."""

from django.contrib import admin
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect
from django.urls import include, path


def root_redirect(_: HttpRequest) -> HttpResponse:
    """Перенаправляет пользователя с корневого URL в раздел упражнений.

    Функция нужна как минимальная точка входа для навигации,
    чтобы кнопки «Назад к упражнениям» имели стабильный маршрут.

    :param _: входящий HTTP-запрос.
    :return: Redirect-ответ на страницу `/games/`.
    """
    return redirect("games")


def games_placeholder(_: HttpRequest) -> HttpResponse:
    """Возвращает заглушку раздела упражнений для текущего этапа.

    Заглушка используется только как навигационный якорь для
    пользовательских страниц энциклопедии до реализации полного
    функционала сценариев и игр.

    :param _: входящий HTTP-запрос.
    :return: Текстовый HTTP-ответ.
    """
    return HttpResponse("Раздел упражнений")


urlpatterns = [
    path("", root_redirect, name="root"),
    path("admin/", admin.site.urls),
    path("games/", games_placeholder, name="games"),
    path("knowledge-base/", include("encyclopedia.urls")),
    path("accounts/", include("django.contrib.auth.urls")),
]
