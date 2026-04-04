"""Пользовательские представления раздела энциклопедии."""

from __future__ import annotations

from dataclasses import dataclass

from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, render

from encyclopedia.models import EncyclopediaArticle


@dataclass(frozen=True)
class _SortingToken:
    """Вспомогательная структура для сортировки заголовков статей.

    Нужна для реализации порядка: цифры → кириллица → латиница.

    :param group: Приоритет группы символов.
    :param normalized_title: Нормализованный заголовок для сравнения.
    """

    group: int
    normalized_title: str


def _title_sort_token(title: str) -> _SortingToken:
    """Возвращает токен сортировки для заголовка статьи.

    Порядок групп:
    0 — начинается с цифры,
    1 — начинается с русской буквы,
    2 — начинается с латинской буквы,
    3 — прочие случаи.

    :param title: Заголовок статьи.
    :return: Токен, пригодный для функции `sorted`.
    """
    stripped = (title or "").strip()
    first_char = stripped[0].lower() if stripped else ""
    if first_char.isdigit():
        return _SortingToken(group=0, normalized_title=stripped.lower())
    if "а" <= first_char <= "я" or first_char == "ё":
        return _SortingToken(group=1, normalized_title=stripped.lower())
    if "a" <= first_char <= "z":
        return _SortingToken(group=2, normalized_title=stripped.lower())
    return _SortingToken(group=3, normalized_title=stripped.lower())


@login_required
def article_list(request: HttpRequest) -> HttpResponse:
    """Показывает страницу списка опубликованных статей энциклопедии.

    Представление фильтрует только опубликованные материалы,
    сортирует их по заданному в ТЗ алгоритму и применяет пагинацию
    по 10 элементов на страницу.

    :param request: Входящий HTTP-запрос пользователя.
    :return: HTML-страница списка статей.
    """
    articles = list(EncyclopediaArticle.objects.filter(is_published=True))
    sorted_articles = sorted(articles, key=lambda article: _title_sort_token(article.title))
    paginator = Paginator(sorted_articles, 10)
    page_obj = paginator.get_page(request.GET.get("page"))
    return render(request, "encyclopedia/article_list.html", {"page_obj": page_obj})


@login_required
def article_detail(request: HttpRequest, slug: str) -> HttpResponse:
    """Открывает отдельную страницу опубликованной статьи по slug.

    Доступ к неопубликованным материалам в пользовательском разделе
    запрещён, поэтому выборка включает фильтр `is_published=True`.

    :param request: Входящий HTTP-запрос пользователя.
    :param slug: Уникальный URL-идентификатор статьи.
    :return: HTML-страница содержимого статьи.
    """
    article = get_object_or_404(EncyclopediaArticle, slug=slug, is_published=True)
    return render(request, "encyclopedia/article_detail.html", {"article": article})
