#!/usr/bin/env python
"""Точка входа для запуска административных команд Django-проекта."""

import os
import sys


def main() -> None:
    """Запускает консольные команды Django в контексте текущего проекта.

    Функция используется для локальной разработки и CI-запусков.
    Она выставляет переменную окружения с модулем настроек,
    после чего делегирует выполнение стандартному механизму Django.

    :raises ImportError: Если Django не установлен в активном окружении.
    """
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    from django.core.management import execute_from_command_line

    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
