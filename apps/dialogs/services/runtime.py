"""Сервисные функции старта диалога и обработки сообщений runtime-чата."""

from dataclasses import dataclass
from datetime import timedelta

from django.core.cache import cache
from django.db import transaction
from django.utils import timezone

from apps.content.models import Scenario, ScenarioPrompt
from apps.dialogs.models import (
    DialogMessage,
    DialogMessageRole,
    DialogSession,
    DialogSessionStatus,
)
from apps.platform_config.models import PlatformSettings


@dataclass(slots=True)
class SendMessageResult:
    """Контейнер результата server-side обработки одной реплики пользователя.

    Контекст использования:
        Используется view-слоем JSON endpoint-а ``send-message`` для возврата
        согласованной структуры с пользовательским и ответным сообщением.

    Параметры:
        dialog: Актуализированный объект диалоговой сессии.
        user_message: Сохранённое сообщение пользователя.
        assistant_message: Сохранённый ответ ассистента.

    Возвращаемое значение:
        Экземпляр dataclass с тремя связанными объектами ORM.

    Исключения и особые случаи:
        Исключения обрабатываются сервисом выше уровнем.

    Побочные эффекты:
        Побочные эффекты отсутствуют.
    """

    dialog: DialogSession
    user_message: DialogMessage
    assistant_message: DialogMessage


class DuplicateSubmissionError(Exception):
    """Сигнализирует о параллельной или повторной отправке одного сообщения."""


class DialogNotActiveError(Exception):
    """Сигнализирует о попытке отправки сообщения в неактивный диалог."""


def get_active_platform_settings() -> PlatformSettings | None:
    """Возвращает активные платформенные настройки для snapshot диалога.

    Контекст использования:
        Нужен при старте диалога для фиксации лимитов и LLM-параметров
        в полях ``DialogSession.effective_*``.

    Параметры:
        Параметры отсутствуют.

    Возвращаемое значение:
        Активная запись ``PlatformSettings`` или ``None``.

    Исключения и особые случаи:
        Если настроек нет, вызывающий код использует безопасные дефолты.

    Побочные эффекты:
        Побочные эффекты отсутствуют.
    """

    return PlatformSettings.objects.filter(is_active=True).order_by("-id").first()


def get_active_dialog_for_user(user_id: int) -> DialogSession | None:
    """Возвращает текущий активный диалог пользователя, если он существует.

    Контекст использования:
        Используется в сценарии старта игры, чтобы не создавать второй
        параллельный активный диалог и вернуть пользователя в существующий.

    Параметры:
        user_id: ID пользователя, для которого ищется активный диалог.

    Возвращаемое значение:
        ``DialogSession`` со статусом ``active`` или ``None``.

    Исключения и особые случаи:
        Особые исключения не предусмотрены.

    Побочные эффекты:
        Побочные эффекты отсутствуют.
    """

    return (
        DialogSession.objects.filter(user_id=user_id, status=DialogSessionStatus.ACTIVE)
        .order_by("-started_at")
        .first()
    )


def choose_active_scenario_prompt(scenario: Scenario) -> ScenarioPrompt | None:
    """Выбирает активный игровой промт сценария для старта диалога.

    Контекст использования:
        Применяется перед созданием ``DialogSession`` для фиксации версии промта,
        которая будет использоваться в рамках конкретного диалога.

    Параметры:
        scenario: Сценарий, для которого подбирается активный промт.

    Возвращаемое значение:
        Активный ``ScenarioPrompt`` или ``None``.

    Исключения и особые случаи:
        Если активный промт отсутствует, вызывающий слой должен остановить старт.

    Побочные эффекты:
        Побочные эффекты отсутствуют.
    """

    return (
        scenario.scenario_prompts.filter(is_active=True, is_archived=False)
        .order_by("-updated_at")
        .first()
    )


def create_dialog_session(user_id: int, scenario: Scenario, scenario_prompt: ScenarioPrompt) -> DialogSession:
    """Создаёт новую активную сессию диалога и стартовое сообщение ассистента.

    Контекст использования:
        Используется endpoint-ом старта сценария для инициализации runtime-чата.

    Параметры:
        user_id: ID пользователя-владельца сессии.
        scenario: Выбранный сценарий.
        scenario_prompt: Активный промт сценария на момент старта.

    Возвращаемое значение:
        Созданный объект ``DialogSession``.

    Исключения и особые случаи:
        Потенциальные ошибки целостности БД пробрасываются выше.

    Побочные эффекты:
        Создаёт запись ``DialogSession`` и первое ``DialogMessage``.
    """

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


def build_mock_assistant_reply(user_text: str) -> str:
    """Генерирует временный ответ ассистента для runtime до интеграции LLM.

    Контекст использования:
        Используется на этапе чатового runtime, когда внешний LLM-клиент
        ещё не подключён в отдельной итерации.

    Параметры:
        user_text: Текст последней реплики пользователя.

    Возвращаемое значение:
        Короткий текст ответа ассистента.

    Исключения и особые случаи:
        Пустой текст обрабатывается вызывающим слоем до вызова функции.

    Побочные эффекты:
        Побочные эффекты отсутствуют.
    """

    return f"Понял вас. Уточню: {user_text[:180]}"


def _duplicate_lock_key(dialog_public_id: str) -> str:
    """Возвращает cache-ключ блокировки повторной отправки сообщения.

    Контекст использования:
        Применяется для простой server-side защиты от параллельных POST-запросов.

    Параметры:
        dialog_public_id: Публичный UUID диалога.

    Возвращаемое значение:
        Строковый cache-ключ.

    Исключения и особые случаи:
        Особые исключения отсутствуют.

    Побочные эффекты:
        Побочные эффекты отсутствуют.
    """

    return f"dialog_send_lock:{dialog_public_id}"


def send_user_message(dialog: DialogSession, text: str) -> SendMessageResult:
    """Сохраняет реплику пользователя и создаёт один ответ ассистента.

    Контекст использования:
        Используется JSON endpoint-ом ``send-message`` для базового цикла
        чата «user -> assistant» на одной странице без перезагрузки.

    Параметры:
        dialog: Активный диалог пользователя.
        text: Текст пользовательской реплики.

    Возвращаемое значение:
        ``SendMessageResult`` с обновлённой сессией и двумя сообщениями.

    Исключения и особые случаи:
        Выбрасывает ``DialogNotActiveError`` и ``DuplicateSubmissionError``
        при нарушении статуса или повторной отправке.

    Побочные эффекты:
        Создаёт две записи ``DialogMessage`` и обновляет счётчики диалога.
    """

    if dialog.status != DialogSessionStatus.ACTIVE:
        raise DialogNotActiveError

    lock_key = _duplicate_lock_key(str(dialog.public_id))
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

            assistant_text = build_mock_assistant_reply(text)
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


def compute_seconds_remaining(dialog: DialogSession) -> int:
    """Вычисляет оставшееся время активного диалога в секундах.

    Контекст использования:
        Нужно для отрисовки таймера на странице чата и JSON-ответов runtime.

    Параметры:
        dialog: Текущая диалоговая сессия.

    Возвращаемое значение:
        Неотрицательное целое число секунд до истечения лимита.

    Исключения и особые случаи:
        Для неактивного диалога возвращается ``0``.

    Побочные эффекты:
        Побочные эффекты отсутствуют.
    """

    if dialog.status != DialogSessionStatus.ACTIVE:
        return 0
    deadline = dialog.started_at + timedelta(seconds=dialog.effective_duration_seconds)
    return max(0, int((deadline - timezone.now()).total_seconds()))
