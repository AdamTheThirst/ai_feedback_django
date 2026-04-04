"""Сервисные функции безопасного технического журналирования в БД."""

from __future__ import annotations

import traceback
from typing import Any

from apps.analysis.models import AnalysisRun
from apps.auditlog.models import AuditLogEntry, AuditLogLevel
from apps.dialogs.models import DialogSession


def log_audit_event(
    *,
    level: str,
    event_type: str,
    message: str,
    actor_user_id: int | None = None,
    dialog: DialogSession | None = None,
    analysis_run: AnalysisRun | None = None,
    object_type: str = "",
    object_id: str = "",
    context_json: dict[str, Any] | None = None,
    exception: Exception | None = None,
) -> None:
    """Пишет техническое событие в аудит-лог без риска обрушить бизнес-поток.

    Контекст использования:
        Используется runtime-, analysis- и security-слоями для централизованной
        фиксации ошибок и подозрительных действий, не прерывая основной сценарий.

    Параметры:
        level: Уровень события из ``AuditLogLevel``.
        event_type: Короткий машинно-читаемый код события.
        message: Человекочитаемое описание инцидента.
        actor_user_id: ID пользователя-инициатора, если известен.
        dialog: Связанный диалог, если событие относится к конкретной сессии.
        analysis_run: Связанный запуск анализа, если применимо.
        object_type: Тип предметного объекта для дополнительной фильтрации.
        object_id: Идентификатор предметного объекта.
        context_json: Дополнительные диагностические поля.
        exception: Исходное исключение для сохранения traceback.

    Возвращаемое значение:
        Ничего не возвращает.

    Исключения и особые случаи:
        Любые исключения записи в БД подавляются, чтобы не ломать пользовательский flow.

    Побочные эффекты:
        Создаёт запись ``AuditLogEntry`` в БД при успешной операции.
    """

    traceback_text = ""
    if exception is not None:
        traceback_text = "".join(traceback.format_exception(type(exception), exception, exception.__traceback__))

    try:
        AuditLogEntry.objects.create(
            level=level,
            event_type=event_type,
            message=message,
            actor_user_id=actor_user_id,
            dialog=dialog,
            analysis_run=analysis_run,
            object_type=object_type,
            object_id=object_id,
            context_json=context_json or {},
            traceback_text=traceback_text,
        )
    except Exception:
        return


def log_security_warning(
    *,
    event_type: str,
    message: str,
    actor_user_id: int | None = None,
    dialog: DialogSession | None = None,
    context_json: dict[str, Any] | None = None,
    exception: Exception | None = None,
) -> None:
    """Логирует предупреждение по безопасности как ``warning``-событие.

    Контекст использования:
        Упрощает единообразную запись security-инцидентов (доступ, rate-limit,
        подозрительные payload) с минимальным количеством кода во view-слое.

    Параметры:
        event_type: Машинный код события безопасности.
        message: Краткое человекочитаемое описание события.
        actor_user_id: ID пользователя-инициатора, если доступен.
        dialog: Связанный диалог, если событие относится к нему.
        context_json: Дополнительный контекст события.
        exception: Исключение, если нужно сохранить traceback.

    Возвращаемое значение:
        Ничего не возвращает.

    Исключения и особые случаи:
        Внутренние ошибки логирования подавляются внутри ``log_audit_event``.

    Побочные эффекты:
        Создаёт запись в ``AuditLogEntry`` с уровнем ``warning``.
    """

    log_audit_event(
        level=AuditLogLevel.WARNING,
        event_type=event_type,
        message=message,
        actor_user_id=actor_user_id,
        dialog=dialog,
        context_json=context_json,
        exception=exception,
    )
