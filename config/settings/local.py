"""Настройки локальной разработки для запуска проекта на машине разработчика."""

from .base import *  # noqa: F403

DEBUG = True

ALLOWED_HOSTS = ["127.0.0.1", "localhost"]

SECRET_KEY = "dev-local-secret-key"
