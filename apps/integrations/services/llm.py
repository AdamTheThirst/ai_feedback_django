"""Клиент и обёртки вызова OpenAI-compatible LLM (vLLM)."""

from __future__ import annotations

import os
from dataclasses import dataclass

from openai import OpenAI

from apps.platform_config.models import PlatformSettings


class LLMConfigurationError(Exception):
    """Ошибка конфигурации LLM-клиента при отсутствии обязательных параметров.

    Контекст использования:
        Выбрасывается, если не удалось собрать корректные ``base_url``/``api_key``
        для соединения с OpenAI-compatible endpoint.

    Параметры:
        Использует стандартные параметры ``Exception``.

    Возвращаемое значение:
        Экземпляр исключения.

    Исключения и особые случаи:
        Особые случаи отсутствуют.

    Побочные эффекты:
        Побочные эффекты отсутствуют.
    """


def _env_value_with_aliases(primary_name: str, *alias_names: str) -> str:
    """Возвращает первую непустую переменную окружения из списка имён.

    Контекст использования:
        Нужен для плавной поддержки разных схем именования env-переменных
        (``LLM_*`` и совместимые ``OPENAI_*``) без дублирования логики в
        конфигураторе запроса.

    Параметры:
        primary_name: Основное имя переменной окружения.
        *alias_names: Дополнительные совместимые имена в порядке приоритета.

    Возвращаемое значение:
        Строка со значением первой найденной непустой переменной или пустая
        строка, если значения не задано.

    Исключения и особые случаи:
        Исключения не выбрасываются; отсутствующие переменные считаются
        нормальным сценарием.

    Побочные эффекты:
        Читает значения из ``os.environ``.
    """

    for env_name in (primary_name, *alias_names):
        value = os.getenv(env_name, "").strip()
        if value:
            return value
    return ""


@dataclass(slots=True)
class LLMRequestConfig:
    """Конфигурация одного LLM-вызова для диалога или аналитики.

    Контекст использования:
        Собирается из env + активных ``PlatformSettings`` и передаётся в
        единый метод ``call_chat_completion``.

    Параметры:
        base_url: URL OpenAI-compatible API (vLLM).
        api_key: API-ключ доступа.
        model_name: Имя модели.
        temperature: Температура генерации.
        top_p: Параметр top-p.
        max_tokens: Лимит токенов на ответ.

    Возвращаемое значение:
        Dataclass с готовыми параметрами запроса.

    Исключения и особые случаи:
        Особые исключения отсутствуют.

    Побочные эффекты:
        Побочные эффекты отсутствуют.
    """

    base_url: str
    api_key: str
    model_name: str
    temperature: float
    top_p: float
    max_tokens: int


def _build_request_config(settings: PlatformSettings | None, *, for_analysis: bool) -> LLMRequestConfig:
    """Собирает параметры LLM-вызова с безопасным приоритетом env.

    Контекст использования:
        Позволяет хранить секреты в окружении (``.env``) и использовать
        ``PlatformSettings`` как управляемый fallback для dev/админки.

    Параметры:
        settings: Активные платформенные настройки или ``None``.
        for_analysis: ``True`` для аналитического вызова, иначе диалоговый.

    Возвращаемое значение:
        Заполненный ``LLMRequestConfig``.

    Исключения и особые случаи:
        Выбрасывает ``LLMConfigurationError``, если не найден ``base_url``.

    Побочные эффекты:
        Читает переменные окружения процесса.
    """

    base_url = (_env_value_with_aliases("LLM_BASE_URL", "OPENAI_BASE_URL") or (settings.llm_base_url if settings else "")).strip()
    api_key = (_env_value_with_aliases("LLM_API_KEY", "OPENAI_API_KEY") or (settings.llm_api_key if settings else "")).strip()
    model_name = (
        _env_value_with_aliases("LLM_MODEL_NAME", "OPENAI_MODEL")
        or (settings.llm_model_name if settings else "Qwen/Qwen3-32B")
    ).strip()

    if not base_url:
        raise LLMConfigurationError("Не настроен LLM_BASE_URL/OPENAI_BASE_URL (env или PlatformSettings).")

    temperature = float(settings.llm_temperature) if settings else 0.7
    top_p = float(settings.llm_top_p) if settings else 0.8
    max_tokens = int(settings.llm_analysis_max_tokens if for_analysis else settings.llm_game_max_tokens) if settings else (2500 if for_analysis else 1500)

    return LLMRequestConfig(
        base_url=base_url,
        api_key=api_key,
        model_name=model_name,
        temperature=temperature,
        top_p=top_p,
        max_tokens=max_tokens,
    )


def call_chat_completion(messages: list[dict[str, str]], settings: PlatformSettings | None, *, for_analysis: bool) -> str:
    """Выполняет синхронный chat completion запрос к OpenAI-compatible API.

    Контекст использования:
        Применяется рантайм-диалогом и аналитическим раннером как единая точка
        интеграции с внешним LLM-сервером.

    Параметры:
        messages: Список сообщений в формате OpenAI Chat Completions.
        settings: Активные платформенные настройки.
        for_analysis: Признак аналитического вызова для выбора max_tokens.

    Возвращаемое значение:
        Текстовый ответ модели (``choices[0].message.content``).

    Исключения и особые случаи:
        Может выбрасывать ошибки клиента OpenAI/HTTP и ``LLMConfigurationError``.

    Побочные эффекты:
        Выполняет сетевой запрос к внешнему LLM endpoint.
    """

    request_config = _build_request_config(settings=settings, for_analysis=for_analysis)
    client = OpenAI(base_url=request_config.base_url, api_key=request_config.api_key)

    response = client.chat.completions.create(
        model=request_config.model_name,
        messages=messages,
        max_tokens=request_config.max_tokens,
        temperature=request_config.temperature,
        top_p=request_config.top_p,
    )
    return (response.choices[0].message.content or "").strip()
