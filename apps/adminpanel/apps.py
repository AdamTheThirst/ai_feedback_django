"""Конфигурация приложения adminpanel."""

from django.apps import AppConfig


class AdminpanelConfig(AppConfig):
    """Описывает параметры инициализации приложения adminpanel.

    Контекст использования:
        Подключается в ``INSTALLED_APPS`` для регистрации модуля админ-панели.

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
    name = "apps.adminpanel"
    verbose_name = "Админ-панель"
