"""Конфигурация приложения platform_config."""

from django.apps import AppConfig


class PlatformConfigConfig(AppConfig):
    """Описывает параметры инициализации приложения platform_config.

    Контекст использования:
        Подключается в ``INSTALLED_APPS`` для регистрации модуля настроек.

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
    name = "apps.platform_config"
    verbose_name = "Настройки платформы"
