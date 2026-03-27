"""Сервис синхронного запуска аналитики и устойчивой обработки JSON-ответов."""

import json
from dataclasses import dataclass

from django.db import transaction
from django.utils import timezone

from apps.analysis.models import (
    AnalysisResult,
    AnalysisRun,
    AnalysisRunStatus,
    AnalysisValidationStatus,
)
from apps.auditlog.models import AuditLogLevel
from apps.auditlog.services import log_audit_event
from apps.content.models import AnalysisPrompt
from apps.dialogs.models import DialogSession

MAX_ANALYSIS_ATTEMPTS = 2


@dataclass(slots=True)
class ParsedAnalysisPayload:
    """Контейнер разобранного JSON ответа аналитического критерия."""

    rating: int
    text: str


class InvalidJSONError(Exception):
    """Ошибка синтаксически невалидного JSON ответа аналитического вызова."""


class InvalidSchemaError(Exception):
    """Ошибка несоответствия JSON минимальному контракту аналитики."""



def _build_dialog_transcript(dialog: DialogSession) -> str:
    """Собирает текстовую стенограмму диалога для передачи в анализ.

    Контекст использования:
        Используется при формировании входного контекста каждого аналитического
        промта во время синхронного запуска анализа.

    Параметры:
        dialog: Диалоговая сессия, по которой запускается анализ.

    Возвращаемое значение:
        Строка стенограммы в формате ``role: text`` по всем сообщениям.

    Исключения и особые случаи:
        При пустом наборе сообщений возвращается пустая строка.

    Побочные эффекты:
        Побочные эффекты отсутствуют.
    """

    parts: list[str] = []
    for message in dialog.messages.order_by("sequence_no"):
        parts.append(f"{message.role}: {message.text}")
    return "\n".join(parts)


def _mock_analysis_llm_response(prompt: AnalysisPrompt, transcript: str, attempt: int) -> str:
    """Возвращает мок-ответ аналитической LLM для текущей итерации разработки.

    Контекст использования:
        Временная реализация до подключения внешнего LLM-клиента.

    Параметры:
        prompt: Аналитический критерий.
        transcript: Полный транскрипт диалога.
        attempt: Номер текущей попытки вызова.

    Возвращаемое значение:
        JSON-строка или намеренно невалидная строка для сценариев устойчивости.

    Исключения и особые случаи:
        Если в тексте промта есть маркер ``[[invalid_json_once]]``, первая попытка
        возвращает невалидный JSON для проверки retry-стратегии.

    Побочные эффекты:
        Побочные эффекты отсутствуют.
    """

    if "[[invalid_json_once]]" in prompt.prompt_text and attempt == 1:
        return "{rating: 3, text: invalid}"

    if "[[invalid_schema_once]]" in prompt.prompt_text and attempt == 1:
        return json.dumps({"score": 3, "message": "Схема неверная"}, ensure_ascii=False)

    span = max(1, prompt.max_rating - prompt.min_rating + 1)
    rating = prompt.min_rating + (len(transcript) % span)
    return json.dumps(
        {
            "rating": int(rating),
            "text": f"Критерий «{prompt.title}»: зафиксированы реплики и контекст диалога.",
        },
        ensure_ascii=False,
    )


def _parse_analysis_json(raw_text: str) -> ParsedAnalysisPayload:
    """Проверяет и нормализует JSON-ответ аналитического критерия.

    Контекст использования:
        Центральная точка валидации контрактов ``rating/text`` для анализа.

    Параметры:
        raw_text: Сырой текст ответа LLM.

    Возвращаемое значение:
        Нормализованный dataclass ``ParsedAnalysisPayload``.

    Исключения и особые случаи:
        Выбрасывает ``InvalidJSONError`` и ``InvalidSchemaError``.

    Побочные эффекты:
        Побочные эффекты отсутствуют.
    """

    try:
        payload = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise InvalidJSONError("Ответ не является валидным JSON.") from exc

    if not isinstance(payload, dict):
        raise InvalidSchemaError("Корневой JSON должен быть объектом.")

    rating = payload.get("rating")
    text = payload.get("text")

    if not isinstance(rating, int):
        raise InvalidSchemaError("Поле rating должно быть целым числом.")
    if not isinstance(text, str) or not text.strip():
        raise InvalidSchemaError("Поле text должно быть непустой строкой.")

    return ParsedAnalysisPayload(rating=rating, text=text.strip())


def _save_audit_event(event_type: str, message: str, dialog: DialogSession, context_json: dict) -> None:
    """Сохраняет техническое событие аналитики в аудит-лог.

    Контекст использования:
        Используется при ошибках JSON/схемы и аварийных состояниях анализа.

    Параметры:
        event_type: Тип события для журнала.
        message: Краткое описание события.
        dialog: Связанный диалог.
        context_json: Диагностический JSON-контекст.

    Возвращаемое значение:
        Ничего не возвращает.

    Исключения и особые случаи:
        Ошибки логирования не обрабатываются на этом уровне.

    Побочные эффекты:
        Создаёт запись ``AuditLogEntry`` в БД.
    """

    log_audit_event(
        level=AuditLogLevel.WARNING,
        event_type=event_type,
        message=message,
        actor_user_id=dialog.user_id,
        dialog=dialog,
        context_json=context_json,
    )


def run_analysis_for_dialog(dialog: DialogSession) -> AnalysisRun | None:
    """Синхронно запускает анализ по активным критериям игры диалога.

    Контекст использования:
        Вызывается при завершении или прерывании диалога, если у пользователя
        была хотя бы одна реплика и анализ требуется по бизнес-правилам.

    Параметры:
        dialog: Диалоговая сессия для анализа.

    Возвращаемое значение:
        Созданный/обновлённый ``AnalysisRun`` или ``None`` при пропуске.

    Исключения и особые случаи:
        При ``user_message_count == 0`` анализ не запускается и возвращается ``None``.

    Побочные эффекты:
        Создаёт ``AnalysisRun`` и ``AnalysisResult``, обновляет статус анализа,
        пишет технические события в ``AuditLogEntry``.
    """

    if dialog.user_message_count == 0:
        return None

    with transaction.atomic():
        analysis_run, _ = AnalysisRun.objects.get_or_create(
            dialog=dialog,
            defaults={
                "status": AnalysisRunStatus.PENDING,
                "started_at": timezone.now(),
                "llm_attempt_count": 0,
            },
        )

        if analysis_run.status == AnalysisRunStatus.COMPLETED:
            return analysis_run

        analysis_run.status = AnalysisRunStatus.RUNNING
        analysis_run.started_at = analysis_run.started_at or timezone.now()
        analysis_run.error_code = ""
        analysis_run.error_message = ""
        analysis_run.save(update_fields=["status", "started_at", "error_code", "error_message", "updated_at"])

        transcript = _build_dialog_transcript(dialog)
        prompts = AnalysisPrompt.objects.filter(
            game=dialog.game,
            is_active=True,
            is_archived=False,
        ).order_by("sort_order", "id")

        for prompt in prompts:
            parsed_payload: ParsedAnalysisPayload | None = None
            raw_response = ""
            validation_status = AnalysisValidationStatus.VALID
            validation_error = ""
            attempts = 0

            for attempt in range(1, MAX_ANALYSIS_ATTEMPTS + 1):
                attempts = attempt
                raw_response = _mock_analysis_llm_response(prompt=prompt, transcript=transcript, attempt=attempt)
                analysis_run.llm_attempt_count += 1

                try:
                    parsed_payload = _parse_analysis_json(raw_response)
                    if not (prompt.min_rating <= parsed_payload.rating <= prompt.max_rating):
                        raise InvalidSchemaError("rating выходит за диапазон критерия.")
                    break
                except InvalidJSONError as exc:
                    validation_status = AnalysisValidationStatus.INVALID_JSON
                    validation_error = str(exc)
                    _save_audit_event(
                        event_type="analysis.invalid_json",
                        message="Получен невалидный JSON от анализа.",
                        dialog=dialog,
                        context_json={"analysis_prompt_alias": prompt.alias, "attempt": attempt},
                    )
                except InvalidSchemaError as exc:
                    validation_status = AnalysisValidationStatus.INVALID_SCHEMA
                    validation_error = str(exc)
                    _save_audit_event(
                        event_type="analysis.invalid_schema",
                        message="JSON анализа не прошёл проверку схемы.",
                        dialog=dialog,
                        context_json={"analysis_prompt_alias": prompt.alias, "attempt": attempt},
                    )

            if parsed_payload is None:
                validation_status = AnalysisValidationStatus.FALLBACK_SAVED
                parsed_payload = ParsedAnalysisPayload(
                    rating=prompt.min_rating,
                    text="Не удалось корректно разобрать ответ анализа. Сохранён fallback-результат.",
                )

            AnalysisResult.objects.update_or_create(
                analysis_run=analysis_run,
                analysis_prompt=prompt,
                defaults={
                    "sort_order_snapshot": prompt.sort_order,
                    "alias_snapshot": prompt.alias,
                    "title_snapshot": prompt.title,
                    "header_snapshot_text": prompt.header_text,
                    "comment_snapshot_text": prompt.comment_text,
                    "rating": parsed_payload.rating,
                    "rating_min": prompt.min_rating,
                    "rating_max": prompt.max_rating,
                    "analysis_text": parsed_payload.text,
                    "raw_llm_response_text": raw_response,
                    "parsed_json_snapshot": {
                        "rating": parsed_payload.rating,
                        "text": parsed_payload.text,
                    },
                    "validation_status": validation_status,
                    "validation_error_message": validation_error,
                    "llm_attempt_count": attempts,
                },
            )

        analysis_run.status = AnalysisRunStatus.COMPLETED
        analysis_run.finished_at = timezone.now()
        analysis_run.save(update_fields=["status", "finished_at", "llm_attempt_count", "updated_at"])
        return analysis_run
