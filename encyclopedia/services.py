"""Сервисные функции для генерации summary и безопасной обработки контента."""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from dataclasses import dataclass

from django.conf import settings


CYRILLIC_TO_LATIN_MAP = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e", "ж": "zh",
    "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m", "н": "n", "о": "o",
    "п": "p", "р": "r", "с": "s", "т": "t", "у": "u", "ф": "f", "х": "h", "ц": "ts",
    "ч": "ch", "ш": "sh", "щ": "sch", "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya",
}


@dataclass(frozen=True)
class SummaryGenerationInput:
    """DTO для передачи данных статьи в генератор краткого описания.

    Используется сервисом генерации summary как стабильный контракт
    между модельным уровнем и интеграцией с LLM.

    :param title: Заголовок статьи.
    :param body: Основной текст статьи.
    """

    title: str
    body: str


def transliterate_to_slug_source(value: str) -> str:
    """Преобразует строку с кириллицей в латиницу для генерации slug.

    Функция применяется при автогенерации URL-идентификатора статей.
    Поддерживает базовую транслитерацию русских символов и оставляет
    прочие символы без изменений для последующей очистки slugify.

    :param value: Исходная строка, обычно заголовок статьи.
    :return: Строка после транслитерации кириллицы.
    """
    result: list[str] = []
    for char in value:
        lower = char.lower()
        if lower in CYRILLIC_TO_LATIN_MAP:
            converted = CYRILLIC_TO_LATIN_MAP[lower]
            result.append(converted.upper() if char.isupper() else converted)
        else:
            result.append(char)
    return "".join(result)


def _normalize_summary_text(summary: str) -> str:
    """Нормализует и очищает итоговый summary после генерации.

    В проектном контексте функция удаляет лишние пробелы и переводит
    многострочный ответ модели к однострочному формату без markdown.

    :param summary: Исходный текст summary.
    :return: Очищенный текст summary.
    """
    return re.sub(r"\s+", " ", summary).strip()


def _build_fallback_summary(payload: SummaryGenerationInput) -> str:
    """Создаёт резервное summary без внешнего вызова LLM.

    Функция применяется в случаях, когда интеграция с LLM не настроена
    или внешний вызов недоступен. Текст строится детерминированно
    по заголовку и первым фрагментам статьи.

    :param payload: Заголовок и текст статьи.
    :return: Summary длиной 50–255 символов.
    """
    raw = f"{payload.title}. {payload.body}"
    cleaned = re.sub(r"<[^>]+>", " ", raw)
    cleaned = _normalize_summary_text(cleaned)
    if len(cleaned) < 50:
        cleaned = f"Краткое описание статьи: {cleaned}".strip()
    if len(cleaned) < 50:
        cleaned = (cleaned + " Содержит ключевые рекомендации и объяснения по теме.").strip()
    return cleaned[:255]


def _call_openai_compatible_summary(payload: SummaryGenerationInput) -> str:
    """Вызывает OpenAI-compatible API для генерации краткого описания.

    Используется при наличии настроек LLM в Django settings. В запрос
    передаётся мастер-промт и входные данные статьи. Ожидается ответ
    в формате Chat Completions API.

    :param payload: Заголовок и тело статьи.
    :return: Сгенерированный текст summary.
    :raises RuntimeError: При ошибке HTTP-вызова или неожиданном формате ответа.
    """
    base_url = settings.LLM_SUMMARY_BASE_URL.strip()
    api_key = settings.LLM_SUMMARY_API_KEY.strip()
    model = settings.LLM_SUMMARY_MODEL.strip()
    if not base_url or not api_key or not model:
        raise RuntimeError("Настройки LLM не заполнены")

    prompt = (
        "Ты — редактор деловой базы знаний. "
        "Подготовь одно краткое описание статьи на русском языке, "
        "деловым стилем, без markdown и HTML, длиной 50-255 символов."
    )
    user_content = f"Заголовок: {payload.title}\nТекст: {payload.body}"
    body = json.dumps(
        {
            "model": model,
            "messages": [
                {"role": "system", "content": prompt},
                {"role": "user", "content": user_content},
            ],
            "temperature": 0.2,
        }
    ).encode("utf-8")

    request = urllib.request.Request(
        url=f"{base_url.rstrip('/')}/chat/completions",
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            payload_json = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
        raise RuntimeError("Ошибка обращения к LLM") from error

    try:
        content = payload_json["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as error:
        raise RuntimeError("Некорректный формат ответа LLM") from error
    return _normalize_summary_text(str(content))


def generate_summary(payload: SummaryGenerationInput) -> str:
    """Генерирует summary статьи с fallback-стратегией.

    Функция используется моделью и админ-формой для автоматического
    заполнения/перезаполнения поля summary при создании и редактировании
    статьи. Сначала пытается вызвать OpenAI-compatible endpoint, а при
    ошибке возвращает локально сформированный текст.

    :param payload: Заголовок и текст статьи.
    :return: Summary в допустимых границах длины.
    """
    try:
        summary = _call_openai_compatible_summary(payload)
    except RuntimeError:
        summary = _build_fallback_summary(payload)

    normalized = _normalize_summary_text(summary)
    if len(normalized) < 50:
        normalized = _build_fallback_summary(payload)
    return normalized[:255]
