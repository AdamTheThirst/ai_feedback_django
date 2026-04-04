"""Конфигурация приложения analysis."""

from django.apps import AppConfig


class AnalysisConfig(AppConfig):
    """Описывает параметры инициализации приложения analysis.

    Контекст использования:
        Подключается в ``INSTALLED_APPS`` для регистрации модуля анализа.

    Параметры:
        Использует стандартные параметры ``AppConfig`` Django.

    Возвращаемое значение:
        Экземпляр конфигурации приложения, создаваемый Django автоматически.

    Исключения и особые случаи:
        Специальные исключения не предусмотрены.

    Побочные эффекты:
        Регистрирует метаданные приложения в реестре Django.
    """

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.analysis"
    verbose_name = "Аналитика"
