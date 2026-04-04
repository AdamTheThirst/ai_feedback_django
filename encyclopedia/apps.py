"""Конфигурация Django-приложения энциклопедии."""

from django.apps import AppConfig


class EncyclopediaConfig(AppConfig):
    """Определяет параметры подключения приложения энциклопедии.

    Класс используется Django для регистрации приложения,
    инициализации моделей и подключения административного интерфейса.
    """

    default_auto_field = "django.db.models.BigAutoField"
    name = "encyclopedia"
