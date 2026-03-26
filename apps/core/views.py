"""Представления стартовой страницы, заглушек и технических endpoint-ов."""

from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render

from apps.content.models import Game


def root_entry_view(request: HttpRequest) -> HttpResponse:
    """Перенаправляет пользователя на актуальную точку входа приложения.

    Контекст использования:
        Используется для корневого маршрута ``/`` в соответствии с API-спецификацией,
        где публичный вход должен вести либо на login, либо в защищённую часть.

    Параметры:
        request: Входящий HTTP-запрос.

    Возвращаемое значение:
        Redirect на страницу входа или на главную страницу приложения.

    Исключения и особые случаи:
        Особые исключения отсутствуют.

    Побочные эффекты:
        Побочные эффекты отсутствуют.
    """

    if request.user.is_authenticated:
        return redirect("core:home")
    return redirect("accounts:login")


@login_required
def home_view(request: HttpRequest) -> HttpResponse:
    """Отображает главную страницу с опубликованными играми и сценариями.

    Контекст использования:
        Является основной страницей после входа пользователя в систему.

    Параметры:
        request: HTTP-запрос авторизованного пользователя.

    Возвращаемое значение:
        HTML-страница со списком игр, сценариев и навигацией по заглушкам.

    Исключения и особые случаи:
        Если опубликованных игр нет, отображается информативное пустое состояние.

    Побочные эффекты:
        Побочные эффекты отсутствуют.
    """

    games = (
        Game.objects.filter(is_published=True, is_archived=False)
        .prefetch_related("scenarios")
        .order_by("sort_order", "title")
    )
    return render(request, "core/home.html", {"games": games})


@login_required
def profile_placeholder_view(request: HttpRequest) -> HttpResponse:
    """Показывает заглушку будущего раздела личного кабинета.

    Контекст использования:
        Реализует требование V1 о наличии точки входа в будущий профиль,
        не внедряя полноценный функционал личного кабинета.

    Параметры:
        request: HTTP-запрос авторизованного пользователя.

    Возвращаемое значение:
        HTML-страница-заглушка.

    Исключения и особые случаи:
        Доступ без аутентификации невозможен из-за ``login_required``.

    Побочные эффекты:
        Побочные эффекты отсутствуют.
    """

    return render(request, "core/profile_placeholder.html")


@login_required
def knowledge_base_placeholder_view(request: HttpRequest) -> HttpResponse:
    """Показывает заглушку будущего раздела энциклопедии.

    Контекст использования:
        Реализует требование V1 о наличии точки входа в будущую энциклопедию,
        сохраняя минимальную реализацию без дополнительной бизнес-логики.

    Параметры:
        request: HTTP-запрос авторизованного пользователя.

    Возвращаемое значение:
        HTML-страница-заглушка.

    Исключения и особые случаи:
        Доступ без аутентификации блокируется декоратором ``login_required``.

    Побочные эффекты:
        Побочные эффекты отсутствуют.
    """

    return render(request, "core/knowledge_base_placeholder.html")


def healthcheck_view(request: HttpRequest) -> HttpResponse:
    """Возвращает технический ответ о доступности веб-приложения.

    Контекст использования:
        Применяется как простая smoke-точка для проверки, что Django-проект
        корректно запущен и маршрутизация работает.

    Параметры:
        request: HTTP-запрос от клиента.

    Возвращаемое значение:
        ``HttpResponse`` со статусом 200 и текстом ``ok``.

    Исключения и особые случаи:
        Исключения не ожидаются при штатном выполнении.

    Побочные эффекты:
        Побочные эффекты отсутствуют.
    """

    return HttpResponse("ok")
