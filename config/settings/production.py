"""Шаблон настроек production-окружения для боевого запуска проекта."""

import os

from .base import *  # noqa: F403

DEBUG = False

SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", SECRET_KEY)  # noqa: F405

raw_allowed_hosts = os.getenv("DJANGO_ALLOWED_HOSTS", "")
ALLOWED_HOSTS = [host.strip() for host in raw_allowed_hosts.split(",") if host.strip()]
