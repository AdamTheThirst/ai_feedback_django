"""Модели игрового диалога и сообщений внутри сессии."""

from django.db import models
from django.db.models import Q

from apps.core.models import TimestampedModel, UUIDPublicIdModel


class DialogSessionStatus(models.TextChoices):
    """Перечисляет жизненные состояния игровой диалоговой сессии.

    Контекст использования:
        Используется в ``DialogSession.status`` для ограничения переходов
        между активным и конечными состояниями диалога.

    Параметры:
        Параметры отсутствуют; набор значений фиксирован спецификацией.

    Возвращаемое значение:
        Строковые коды статусов для записи в БД.

    Исключения и особые случаи:
        Особые исключения отсутствуют.

    Побочные эффекты:
        Побочные эффекты отсутствуют.
    """

    ACTIVE = "active", "Активный"
    FINISHED = "finished", "Завершён"
    ABORTED = "aborted", "Прерван"
    ANALYSIS_SKIPPED = "analysis_skipped", "Анализ пропущен"


class DialogEndedReason(models.TextChoices):
    """Определяет причины завершения или прерывания диалоговой сессии.

    Контекст использования:
        Хранится в ``DialogSession.ended_reason`` для диагностики и отчётности
        по пользовательским и техническим завершениям диалога.

    Параметры:
        Параметры отсутствуют.

    Возвращаемое значение:
        Строковые коды причин завершения.

    Исключения и особые случаи:
        Особые исключения отсутствуют.

    Побочные эффекты:
        Побочные эффекты отсутствуют.
    """

    MANUAL_FEEDBACK = "manual_feedback", "Кнопка обратной связи"
    TIMEOUT = "timeout", "Истёк таймер"
    PAGE_LEAVE = "page_leave", "Покинута страница"
    INACTIVE_TIMEOUT = "inactive_timeout", "Серверный таймаут неактивности"
    NO_USER_MESSAGES = "no_user_messages", "Нет пользовательских сообщений"


class DialogMessageRole(models.TextChoices):
    """Задаёт допустимые роли сообщений в игровом транскрипте.

    Контекст использования:
        Используется моделью ``DialogMessage`` для разделения реплик
        пользователя и ассистента в рамках одной сессии.

    Параметры:
        Параметры отсутствуют.

    Возвращаемое значение:
        Строковые значения ролей.

    Исключения и особые случаи:
        Системная роль в таблице сообщений первой версии не используется.

    Побочные эффекты:
        Побочные эффекты отсутствуют.
    """

    ASSISTANT = "assistant", "Ассистент"
    USER = "user", "Пользователь"


class DialogSession(UUIDPublicIdModel, TimestampedModel):
    """Хранит игровую сессию пользователя и её зафиксированные параметры старта.

    Контекст использования:
        Является центральной исторической записью игрового цикла и содержит
        snapshot-параметры, защищающие историю от будущих изменений контента.

    Параметры:
        Создаётся ORM с обязательными ссылками на пользователя, игру, сценарий и промт.

    Возвращаемое значение:
        Экземпляр диалоговой сессии.

    Исключения и особые случаи:
        Ограничение допускает не более одного активного диалога на пользователя.

    Побочные эффекты:
        Используется как родительская сущность для сообщений и анализа.
    """

    user = models.ForeignKey(
        "accounts.User",
        on_delete=models.PROTECT,
        related_name="dialog_sessions",
        verbose_name="Пользователь",
    )
    game = models.ForeignKey(
        "content.Game",
        on_delete=models.PROTECT,
        related_name="dialog_sessions",
        verbose_name="Игра",
    )
    scenario = models.ForeignKey(
        "content.Scenario",
        on_delete=models.PROTECT,
        related_name="dialog_sessions",
        verbose_name="Сценарий",
    )
    scenario_prompt_used = models.ForeignKey(
        "content.ScenarioPrompt",
        on_delete=models.PROTECT,
        related_name="dialog_sessions",
        verbose_name="Использованный игровой промт",
    )
    status = models.CharField(
        max_length=32,
        choices=DialogSessionStatus.choices,
        default=DialogSessionStatus.ACTIVE,
        verbose_name="Статус",
    )
    started_at = models.DateTimeField(verbose_name="Начат")
    ended_at = models.DateTimeField(null=True, blank=True, verbose_name="Завершён")
    ended_reason = models.CharField(
        max_length=64,
        choices=DialogEndedReason.choices,
        blank=True,
        verbose_name="Причина завершения",
    )
    user_message_count = models.PositiveIntegerField(default=0, verbose_name="Сообщений пользователя")
    assistant_message_count = models.PositiveIntegerField(default=0, verbose_name="Сообщений ассистента")
    effective_duration_seconds = models.PositiveIntegerField(verbose_name="Таймер (сек)")
    effective_user_message_max_chars = models.PositiveIntegerField(verbose_name="Лимит пользовательского сообщения")
    effective_game_reply_max_chars = models.PositiveIntegerField(verbose_name="Лимит игрового ответа")
    effective_analysis_reply_max_chars = models.PositiveIntegerField(verbose_name="Лимит аналитического ответа")
    effective_llm_model_name = models.CharField(max_length=255, verbose_name="Модель LLM")
    effective_llm_temperature = models.DecimalField(max_digits=4, decimal_places=2, verbose_name="Temperature")
    effective_llm_top_p = models.DecimalField(max_digits=4, decimal_places=2, verbose_name="Top-p")
    effective_llm_game_max_tokens = models.PositiveIntegerField(verbose_name="Max tokens (игра)")
    effective_llm_analysis_max_tokens = models.PositiveIntegerField(verbose_name="Max tokens (анализ)")
    conditions_snapshot_text = models.TextField(verbose_name="Снимок условий")
    opening_message_snapshot_text = models.TextField(verbose_name="Снимок стартовой реплики")
    last_client_activity_at = models.DateTimeField(null=True, blank=True, verbose_name="Последняя активность клиента")
    client_aborted_at = models.DateTimeField(null=True, blank=True, verbose_name="Клиент сообщил о выходе")

    class Meta:
        """Мета-параметры модели диалоговой сессии."""

        verbose_name = "Диалоговая сессия"
        verbose_name_plural = "Диалоговые сессии"
        ordering = ["-started_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["user"],
                condition=Q(status=DialogSessionStatus.ACTIVE),
                name="dialogs_single_active_session_per_user",
            ),
        ]
        indexes = [
            models.Index(fields=["user", "status"], name="dlg_sess_user_status_idx"),
            models.Index(fields=["game"], name="dialogs_session_game_idx"),
            models.Index(fields=["scenario"], name="dialogs_session_scenario_idx"),
            models.Index(fields=["started_at"], name="dialogs_session_started_idx"),
        ]

    def __str__(self) -> str:
        """Возвращает короткое представление диалоговой сессии.

        Контекст использования:
            Применяется для отладочного и административного вывода объекта.

        Параметры:
            Параметры отсутствуют.

        Возвращаемое значение:
            Строка с идентификатором, пользователем и статусом.

        Исключения и особые случаи:
            Исключения не ожидаются при валидных данных.

        Побочные эффекты:
            Побочные эффекты отсутствуют.
        """

        return f"{self.public_id} / {self.user.email} / {self.status}"


class DialogMessage(models.Model):
    """Хранит отдельную реплику диалога с порядком и ролью отправителя.

    Контекст использования:
        Используется для полного транскрипта переписки, который затем
        передаётся в анализ и экспортируется в итоговый отчёт.

    Параметры:
        Создаётся ORM с обязательной ссылкой на ``DialogSession``.

    Возвращаемое значение:
        Экземпляр сообщения диалога.

    Исключения и особые случаи:
        Уникальность ``(dialog, sequence_no)`` защищает последовательность сообщений.

    Побочные эффекты:
        При удалении диалога его сообщения удаляются каскадно.
    """

    dialog = models.ForeignKey(
        "dialogs.DialogSession",
        on_delete=models.CASCADE,
        related_name="messages",
        verbose_name="Диалог",
    )
    sequence_no = models.PositiveIntegerField(verbose_name="Порядковый номер")
    role = models.CharField(max_length=32, choices=DialogMessageRole.choices, verbose_name="Роль")
    text = models.TextField(verbose_name="Текст")
    char_count = models.PositiveIntegerField(verbose_name="Количество символов")
    llm_request_id = models.CharField(max_length=255, blank=True, verbose_name="ID LLM-запроса")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Создано")

    class Meta:
        """Мета-параметры модели сообщения диалога."""

        verbose_name = "Сообщение диалога"
        verbose_name_plural = "Сообщения диалога"
        ordering = ["dialog", "sequence_no"]
        constraints = [
            models.UniqueConstraint(
                fields=["dialog", "sequence_no"],
                name="dialogs_message_unique_sequence_per_dialog",
            ),
        ]
        indexes = [
            models.Index(fields=["dialog", "sequence_no"], name="dialogs_message_dialog_seq_idx"),
        ]

    def __str__(self) -> str:
        """Возвращает короткое представление сообщения для админского вывода.

        Контекст использования:
            Применяется в журналировании и административных списках сообщений.

        Параметры:
            Параметры отсутствуют.

        Возвращаемое значение:
            Строка с публичным ID диалога и номером сообщения.

        Исключения и особые случаи:
            Исключения не ожидаются.

        Побочные эффекты:
            Побочные эффекты отсутствуют.
        """

        return f"{self.dialog.public_id} #{self.sequence_no}"
