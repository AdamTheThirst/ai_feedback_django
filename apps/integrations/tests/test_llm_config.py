"""Тесты сборки конфигурации LLM с поддержкой env-алиасов."""

import os
from unittest.mock import patch

from django.test import SimpleTestCase

from apps.integrations.services.llm import LLMConfigurationError, _build_request_config


class LLMConfigBuildTests(SimpleTestCase):
    """Проверяет приоритет env-переменных и fallback к значениям по умолчанию.

    Контекст использования:
        Фиксирует контракт формирования ``LLMRequestConfig`` для runtime- и
        аналитических вызовов, когда параметры берутся из окружения процесса.

    Параметры:
        Использует ``SimpleTestCase`` без доступа к БД и ``patch.dict`` для
        изоляции окружения между тестами.

    Возвращаемое значение:
        Не возвращает значение; выполняет набор unit-проверок.

    Исключения и особые случаи:
        Любое нарушение ожидаемой приоритетности параметров приводит к падению.

    Побочные эффекты:
        Временно меняет ``os.environ`` на время отдельных тестов.
    """

    def test_build_request_config_uses_openai_aliases_from_env(self) -> None:
        """Проверяет чтение OPENAI-алиасов при отсутствии LLM-переменных.

        Контекст использования:
            В локальных окружениях часто используются имена ``OPENAI_*``;
            тест гарантирует, что они поддерживаются как совместимые алиасы.

        Параметры:
            Параметры отсутствуют.

        Возвращаемое значение:
            Ничего не возвращает.

        Исключения и особые случаи:
            Исключения не ожидаются.

        Побочные эффекты:
            На время теста подменяет ``os.environ``.
        """

        with patch.dict(
            os.environ,
            {
                "OPENAI_BASE_URL": "https://llm.local/v1",
                "OPENAI_API_KEY": "alias-key",
                "OPENAI_MODEL": "Qwen/Qwen3-32B",
            },
            clear=True,
        ):
            config = _build_request_config(settings=None, for_analysis=False)

        self.assertEqual(config.base_url, "https://llm.local/v1")
        self.assertEqual(config.api_key, "alias-key")
        self.assertEqual(config.model_name, "Qwen/Qwen3-32B")

    def test_build_request_config_prefers_llm_env_over_openai_alias(self) -> None:
        """Проверяет приоритет ``LLM_*`` над совместимыми ``OPENAI_*``.

        Контекст использования:
            Предотвращает неоднозначность при одновременном наличии двух схем
            переменных окружения в одном процессе.

        Параметры:
            Параметры отсутствуют.

        Возвращаемое значение:
            Ничего не возвращает.

        Исключения и особые случаи:
            Исключения не ожидаются.

        Побочные эффекты:
            На время теста подменяет ``os.environ``.
        """

        with patch.dict(
            os.environ,
            {
                "LLM_BASE_URL": "https://llm.primary/v1",
                "OPENAI_BASE_URL": "https://llm.alias/v1",
                "LLM_API_KEY": "primary-key",
                "OPENAI_API_KEY": "alias-key",
                "LLM_MODEL_NAME": "primary-model",
                "OPENAI_MODEL": "alias-model",
            },
            clear=True,
        ):
            config = _build_request_config(settings=None, for_analysis=True)

        self.assertEqual(config.base_url, "https://llm.primary/v1")
        self.assertEqual(config.api_key, "primary-key")
        self.assertEqual(config.model_name, "primary-model")
        self.assertEqual(config.max_tokens, 2500)

    def test_build_request_config_raises_when_no_base_url_anywhere(self) -> None:
        """Проверяет ошибку конфигурации при пустом URL LLM endpoint-а.

        Контекст использования:
            Гарантирует раннее и понятное падение интеграции, если ни env, ни
            platform fallback не содержит обязательный ``base_url``.

        Параметры:
            Параметры отсутствуют.

        Возвращаемое значение:
            Ничего не возвращает.

        Исключения и особые случаи:
            Ожидается ``LLMConfigurationError``.

        Побочные эффекты:
            На время теста очищает ``os.environ``.
        """

        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(LLMConfigurationError):
                _build_request_config(settings=None, for_analysis=False)
