"""Представления списка игр и страницы отдельной игры со сценариями."""

from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, render

from apps.content.models import Game


@login_required
def game_list_view(request: HttpRequest) -> HttpResponse:
    """Показывает список опубликованных игр, доступных пользователю.

    Контекст использования:
        Является основным пользовательским экраном после входа в систему.

    Параметры:
        request: HTTP-запрос авторизованного пользователя.

    Возвращаемое значение:
        HTML-страница списка игр.

    Исключения и особые случаи:
        При отсутствии опубликованных игр рендерится пустое состояние.

    Побочные эффекты:
        Побочные эффекты отсутствуют.
    """

    games = (
        Game.objects.filter(is_published=True, is_archived=False)
        .prefetch_related("scenarios")
        .order_by("sort_order", "title")
    )
    return render(request, "content/game_list.html", {"games": games})


@login_required
def game_detail_view(request: HttpRequest, game_slug: str) -> HttpResponse:
    """Показывает страницу конкретной игры и её активные сценарии.

    Контекст использования:
        Используется как промежуточный экран выбора сценария перед стартом чата.

    Параметры:
        request: HTTP-запрос авторизованного пользователя.
        game_slug: Slug выбранной игры.

    Возвращаемое значение:
        HTML-страница игры со списком сценариев.

    Исключения и особые случаи:
        Возвращает 404 при недоступной или архивной игре.

    Побочные эффекты:
        Побочные эффекты отсутствуют.
    """

    game = get_object_or_404(Game, slug=game_slug, is_published=True, is_archived=False)
    scenarios = game.scenarios.filter(is_published=True, is_archived=False).order_by("sort_order", "title")
    return render(request, "content/game_detail.html", {"game": game, "scenarios": scenarios})
