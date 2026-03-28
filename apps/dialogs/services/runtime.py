"""Сервисные функции старта диалога, отправки сообщений и завершения сессии."""

from dataclasses import dataclass
from datetime import timedelta

from django.core.cache import cache
from django.db import transaction
from django.utils import timezone

from apps.auditlog.models import AuditLogLevel
from apps.auditlog.services import log_audit_event
from apps.content.models import Scenario, ScenarioPrompt
from apps.dialogs.models import (
    DialogEndedReason,
    DialogMessage,
    DialogMessageRole,
    DialogSession,
    DialogSessionStatus,
)
from apps.integrations.services.llm import LLMConfigurationError, call_chat_completion
from apps.platform_config.models import PlatformSettings


@dataclass(slots=True)
class SendMessageResult:
    """Контейнер результата server-side обработки одной реплики пользователя."""

    dialog: DialogSession
    user_message: DialogMessage
    assistant_message: DialogMessage


class DuplicateSubmissionError(Exception):
    """Сигнализирует о параллельной или повторной отправке одного сообщения."""


class DialogNotActiveError(Exception):
    """Сигнализирует о попытке операции в неактивном диалоге."""


class DuplicateFinishError(Exception):
    """Сигнализирует о параллельной попытке завершения одного диалога."""


LLM_DIALOG_ATTEMPTS = 2


def get_active_platform_settings() -> PlatformSettings | None:
    """Возвращает активные платформенные настройки для snapshot диалога."""

    return PlatformSettings.objects.filter(is_active=True).order_by("-id").first()


def get_active_dialog_for_user(user_id: int) -> DialogSession | None:
    """Возвращает текущий активный диалог пользователя, если он существует."""

    return (
        DialogSession.objects.filter(user_id=user_id, status=DialogSessionStatus.ACTIVE)
        .order_by("-started_at")
        .first()
    )


def choose_active_scenario_prompt(scenario: Scenario) -> ScenarioPrompt | None:
    """Выбирает активный игровой промт сценария для старта диалога."""

    return (
        scenario.scenario_prompts.filter(is_active=True, is_archived=False)
        .order_by("-updated_at")
        .first()
    )


def create_dialog_session(user_id: int, scenario: Scenario, scenario_prompt: ScenarioPrompt) -> DialogSession:
    """Создаёт новую активную сессию диалога и стартовое сообщение ассистента."""

    settings = get_active_platform_settings()
    duration_minutes = settings.default_dialog_duration_minutes if settings else 10
    dialog = DialogSession.objects.create(
        user_id=user_id,
        game=scenario.game,
        scenario=scenario,
        scenario_prompt_used=scenario_prompt,
        status=DialogSessionStatus.ACTIVE,
        started_at=timezone.now(),
        user_message_count=0,
        assistant_message_count=1,
        effective_duration_seconds=duration_minutes * 60,
        effective_user_message_max_chars=(settings.max_user_message_chars if settings else 2500),
        effective_game_reply_max_chars=(settings.max_game_reply_chars if settings else 3500),
        effective_analysis_reply_max_chars=(settings.max_analysis_reply_chars if settings else 4500),
        effective_llm_model_name=(settings.llm_model_name if settings else "Qwen/Qwen3-32B"),
        effective_llm_temperature=(settings.llm_temperature if settings else 0.7),
        effective_llm_top_p=(settings.llm_top_p if settings else 0.8),
        effective_llm_game_max_tokens=(settings.llm_game_max_tokens if settings else 1500),
        effective_llm_analysis_max_tokens=(settings.llm_analysis_max_tokens if settings else 2500),
        conditions_snapshot_text=scenario.conditions_text,
        opening_message_snapshot_text=scenario.opening_message_text,
        last_client_activity_at=timezone.now(),
    )

    DialogMessage.objects.create(
        dialog=dialog,
        sequence_no=1,
        role=DialogMessageRole.ASSISTANT,
        text=dialog.opening_message_snapshot_text,
        char_count=len(dialog.opening_message_snapshot_text),
    )
    return dialog


def _build_dialog_transcript(dialog: DialogSession) -> str:
    """Собирает текущий транскрипт диалога для передачи в LLM.

    Контекст использования:
        Применяется при генерации игрового ответа, чтобы модель видела историю
        реплик пользователя и персонажа в рамках одной сессии.

    Параметры:
        dialog: Текущая диалоговая сессия.

    Возвращаемое значение:
        Текстовый транскрипт в формате ``Роль: текст``.

    Исключения и особые случаи:
        При отсутствии сообщений возвращается пустая строка.

    Побочные эффекты:
        Выполняет чтение связанных сообщений из БД.
    """

    parts: list[str] = []
    for message in dialog.messages.order_by("sequence_no"):
        role = "Пользователь" if message.role == DialogMessageRole.USER else "Персонаж"
        parts.append(f"{role}: {message.text}")
    return "\n".join(parts)


def build_game_llm_messages(dialog: DialogSession, user_text: str) -> list[dict[str, str]]:
    """Формирует список messages для OpenAI-compatible chat completion.

    Контекст использования:
        Используется в runtime-диалоге как единая сборка мастер-контекста:
        игровой промт, условия сценария, стартовое сообщение и транскрипт.

    Параметры:
        dialog: Текущая диалоговая сессия.
        user_text: Последняя реплика пользователя.

    Возвращаемое значение:
        Список словарей ``messages`` для chat completion.

    Исключения и особые случаи:
        Особые исключения отсутствуют.

    Побочные эффекты:
        Читает связанный ``scenario_prompt_used`` и историю сообщений.
    """

    scenario_prompt_text = dialog.scenario_prompt_used.prompt_text
    transcript = _build_dialog_transcript(dialog)
    system_text = (
        "Ты ведёшь ролевой диалог в тренажёре обратной связи.\n"
        f"Игровой промт:\n{scenario_prompt_text}\n\n"
        f"Условия сценария:\n{dialog.conditions_snapshot_text}\n\n"
        f"Стартовая реплика персонажа:\n{dialog.opening_message_snapshot_text}\n\n"
        f"Транскрипт диалога:\n{transcript}\n\n"
        "Отвечай на русском языке. Не выходи из роли."
    )
    return [
        {"role": "system", "content": system_text},
        {"role": "user", "content": user_text},
    ]


def generate_assistant_reply(dialog: DialogSession, user_text: str, settings: PlatformSettings | None) -> str:
    """Генерирует ответ персонажа через внешний LLM с одним retry.

    Контекст использования:
        Вызывается из ``send_user_message`` вместо mock-заглушки и реализует
        требование: повторить LLM-вызов 1 раз, затем вернуть дружелюбную ошибку.

    Параметры:
        dialog: Активный диалог для контекста промта и транскрипта.
        user_text: Последняя реплика пользователя.
        settings: Активные глобальные платформенные настройки.

    Возвращаемое значение:
        Текст ответа ассистента или контролируемая ошибка для пользователя.

    Исключения и особые случаи:
        Внутренние исключения LLM-клиента перехватываются и логируются в аудит.

    Побочные эффекты:
        Выполняет сетевые LLM-запросы и пишет технические события в аудит-лог.
    """

    messages = build_game_llm_messages(dialog=dialog, user_text=user_text)
    last_error: Exception | None = None
    for attempt in range(1, LLM_DIALOG_ATTEMPTS + 1):
        try:
            reply = call_chat_completion(messages=messages, settings=settings, for_analysis=False)
            if reply:
                return reply[: dialog.effective_game_reply_max_chars]
            raise ValueError("LLM вернула пустой ответ в игровом диалоге.")
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            log_audit_event(
                level=AuditLogLevel.WARNING,
                event_type="dialog.llm_error",
                message="Ошибка LLM-вызова при генерации игрового ответа.",
                actor_user_id=dialog.user_id,
                dialog=dialog,
                context_json={"attempt": attempt},
                exception=exc,
            )
            if isinstance(exc, LLMConfigurationError):
                break

    if last_error is not None:
        return "Извините, не удалось получить ответ от модели. Попробуйте отправить сообщение ещё раз."
    return "Извините, временно недоступно. Попробуйте ещё раз."


def _duplicate_lock_key(dialog_public_id: str, action: str) -> str:
    """Возвращает cache-ключ блокировки повторной операции в диалоге."""

    return f"dialog_lock:{action}:{dialog_public_id}"


def send_user_message(dialog: DialogSession, text: str) -> SendMessageResult:
    """Сохраняет реплику пользователя и создаёт один ответ ассистента."""

    if dialog.status != DialogSessionStatus.ACTIVE:
        raise DialogNotActiveError

    lock_key = _duplicate_lock_key(str(dialog.public_id), action="send")
    if not cache.add(lock_key, "1", timeout=5):
        raise DuplicateSubmissionError

    try:
        with transaction.atomic():
            locked_dialog = DialogSession.objects.select_for_update().get(pk=dialog.pk)
            if locked_dialog.status != DialogSessionStatus.ACTIVE:
                raise DialogNotActiveError

            last_sequence_no = (
                DialogMessage.objects.filter(dialog=locked_dialog)
                .order_by("-sequence_no")
                .values_list("sequence_no", flat=True)
                .first()
                or 0
            )

            user_message = DialogMessage.objects.create(
                dialog=locked_dialog,
                sequence_no=last_sequence_no + 1,
                role=DialogMessageRole.USER,
                text=text,
                char_count=len(text),
            )

            settings = get_active_platform_settings()
            assistant_text = generate_assistant_reply(dialog=locked_dialog, user_text=text, settings=settings)
            assistant_message = DialogMessage.objects.create(
                dialog=locked_dialog,
                sequence_no=last_sequence_no + 2,
                role=DialogMessageRole.ASSISTANT,
                text=assistant_text,
                char_count=len(assistant_text),
            )

            locked_dialog.user_message_count += 1
            locked_dialog.assistant_message_count += 1
            locked_dialog.last_client_activity_at = timezone.now()
            locked_dialog.save(
                update_fields=[
                    "user_message_count",
                    "assistant_message_count",
                    "last_client_activity_at",
                    "updated_at",
                ]
            )
            return SendMessageResult(
                dialog=locked_dialog,
                user_message=user_message,
                assistant_message=assistant_message,
            )
    finally:
        cache.delete(lock_key)


def finish_dialog(dialog: DialogSession, reason: str) -> DialogSession:
    """Завершает активный диалог вручную или по таймеру с защитой от дублей."""

    if reason not in {DialogEndedReason.MANUAL_FEEDBACK, DialogEndedReason.TIMEOUT}:
        raise ValueError("Недопустимая причина завершения диалога.")

    lock_key = _duplicate_lock_key(str(dialog.public_id), action="finish")
    if not cache.add(lock_key, "1", timeout=5):
        raise DuplicateFinishError

    try:
        with transaction.atomic():
            locked_dialog = DialogSession.objects.select_for_update().get(pk=dialog.pk)
            if locked_dialog.status != DialogSessionStatus.ACTIVE:
                raise DialogNotActiveError

            if locked_dialog.user_message_count == 0:
                locked_dialog.status = DialogSessionStatus.ANALYSIS_SKIPPED
                locked_dialog.ended_reason = DialogEndedReason.NO_USER_MESSAGES
            else:
                locked_dialog.status = DialogSessionStatus.FINISHED
                locked_dialog.ended_reason = reason

            locked_dialog.ended_at = timezone.now()
            locked_dialog.last_client_activity_at = timezone.now()
            locked_dialog.save(
                update_fields=[
                    "status",
                    "ended_reason",
                    "ended_at",
                    "last_client_activity_at",
                    "updated_at",
                ]
            )
            return locked_dialog
    finally:
        cache.delete(lock_key)


def abandon_dialog(dialog: DialogSession, reason: str = DialogEndedReason.PAGE_LEAVE) -> DialogSession:
    """Прерывает активный диалог при уходе пользователя со страницы чата."""

    if reason not in {DialogEndedReason.PAGE_LEAVE, DialogEndedReason.INACTIVE_TIMEOUT}:
        raise ValueError("Недопустимая причина прерывания диалога.")

    lock_key = _duplicate_lock_key(str(dialog.public_id), action="abandon")
    if not cache.add(lock_key, "1", timeout=5):
        raise DuplicateFinishError

    try:
        with transaction.atomic():
            locked_dialog = DialogSession.objects.select_for_update().get(pk=dialog.pk)
            if locked_dialog.status != DialogSessionStatus.ACTIVE:
                raise DialogNotActiveError

            locked_dialog.status = DialogSessionStatus.ABORTED
            locked_dialog.ended_reason = reason
            now = timezone.now()
            locked_dialog.ended_at = now
            locked_dialog.client_aborted_at = now
            locked_dialog.last_client_activity_at = now
            locked_dialog.save(
                update_fields=[
                    "status",
                    "ended_reason",
                    "ended_at",
                    "client_aborted_at",
                    "last_client_activity_at",
                    "updated_at",
                ]
            )
            return locked_dialog
    finally:
        cache.delete(lock_key)


def compute_seconds_remaining(dialog: DialogSession) -> int:
    """Вычисляет оставшееся время активного диалога в секундах."""

    if dialog.status != DialogSessionStatus.ACTIVE:
        return 0
    deadline = dialog.started_at + timedelta(seconds=dialog.effective_duration_seconds)
    return max(0, int((deadline - timezone.now()).total_seconds()))
