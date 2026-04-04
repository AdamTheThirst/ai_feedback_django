"""Тесты базовых security-настроек Django-конфигурации."""

from django.conf import settings
from django.test import SimpleTestCase


class SecuritySettingsTests(SimpleTestCase):
    """Проверяет, что минимальные параметры hardening включены в настройках.

    Контекст использования:
        Защищает от регрессий, когда критичные флаги cookie/headers случайно
        удаляются при последующих изменениях конфигурации проекта.

    Параметры:
        Использует только in-memory доступ к ``django.conf.settings``.

    Возвращаемое значение:
        Не возвращает значение; выполняет набор assertions.

    Исключения и особые случаи:
        Тест не зависит от БД и может выполняться как unit-проверка.

    Побочные эффекты:
        Побочные эффекты отсутствуют.
    """

    def test_cookie_and_header_hardening_flags_are_enabled(self) -> None:
        """Проверяет включение ключевых security-флагов base-настроек.

        Контекст использования:
            Подтверждает соблюдение минимального уровня безопасных настроек
            для cookie и заголовков в окружениях проекта.

        Параметры:
            Параметры отсутствуют.

        Возвращаемое значение:
            Ничего не возвращает; выполняет проверки boolean/string флагов.

        Исключения и особые случаи:
            При отключении любого флага тест завершается ошибкой.

        Побочные эффекты:
            Побочные эффекты отсутствуют.
        """

        self.assertTrue(settings.SESSION_COOKIE_HTTPONLY)
        self.assertTrue(settings.CSRF_COOKIE_HTTPONLY)
        self.assertEqual(settings.SESSION_COOKIE_SAMESITE, "Lax")
        self.assertEqual(settings.CSRF_COOKIE_SAMESITE, "Lax")
        self.assertTrue(settings.SECURE_CONTENT_TYPE_NOSNIFF)
        self.assertEqual(settings.X_FRAME_OPTIONS, "DENY")
