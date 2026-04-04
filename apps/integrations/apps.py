"""Конфигурация приложения integrations."""

from django.apps import AppConfig


class IntegrationsConfig(AppConfig):
    """Описывает параметры инициализации приложения integrations.

    Контекст использования:
        Подключается в ``INSTALLED_APPS`` для регистрации интеграционного модуля.

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
    name = "apps.integrations"
    verbose_name = "Интеграции"
