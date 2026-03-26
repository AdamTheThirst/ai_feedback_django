#!/usr/bin/env python
"""Точка входа для управления Django-проектом через командную строку."""

import os
import sys


def main() -> None:
    """Запускает выполнение команд Django с локальными настройками по умолчанию.

    Контекст использования:
        Используется разработчиком или CI для выполнения миграций, запуска сервера,
        запуска тестов и других стандартных команд Django.

    Параметры:
        Не принимает явных параметров. Аргументы берутся из ``sys.argv``.

    Возвращаемое значение:
        Ничего не возвращает.

    Исключения и особые случаи:
        Выбрасывает ``ImportError``, если Django не установлен или недоступен.

    Побочные эффекты:
        Устанавливает переменную окружения ``DJANGO_SETTINGS_MODULE`` при её отсутствии
        и передаёт управление в Django CLI.
    """
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Django не установлен или недоступен в текущем окружении."
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
