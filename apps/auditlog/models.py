"""Модель технического журнала значимых событий и ошибок платформы."""

from django.db import models


class AuditLogLevel(models.TextChoices):
    """Перечисляет уровни технической важности записей журналирования.

    Контекст использования:
        Применяется в ``AuditLogEntry.level`` для фильтрации и поиска событий
        в техническом журнале по степени критичности.

    Параметры:
        Параметры отсутствуют.

    Возвращаемое значение:
        Строковые коды уровней логирования.

    Исключения и особые случаи:
        Особые исключения отсутствуют.

    Побочные эффекты:
        Побочные эффекты отсутствуют.
    """

    DEBUG = "debug", "Debug"
    INFO = "info", "Info"
    WARNING = "warning", "Warning"
    ERROR = "error", "Error"
    CRITICAL = "critical", "Critical"


class AuditLogEntry(models.Model):
    """Хранит техническую запись о событии, ошибке или административном действии.

    Контекст использования:
        Используется всеми сервисными модулями для централизованной диагностики
        ошибок LLM, анализа, PDF и других ключевых технических сценариев.

    Параметры:
        Создаётся ORM с уровнем, типом события и текстом сообщения.

    Возвращаемое значение:
        Экземпляр записи технического журнала.

    Исключения и особые случаи:
        Поле ``context_json`` может быть пустым при отсутствии допконтекста.

    Побочные эффекты:
        Логи накапливаются как исторические данные и используются мониторингом.
    """

    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Создано")
    level = models.CharField(max_length=16, choices=AuditLogLevel.choices, verbose_name="Уровень")
    event_type = models.CharField(max_length=128, verbose_name="Тип события")
    message = models.TextField(verbose_name="Сообщение")
    actor_user = models.ForeignKey(
        "accounts.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="audit_log_entries",
        verbose_name="Пользователь-инициатор",
    )
    dialog = models.ForeignKey(
        "dialogs.DialogSession",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="audit_log_entries",
        verbose_name="Диалог",
    )
    analysis_run = models.ForeignKey(
        "analysis.AnalysisRun",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="audit_log_entries",
        verbose_name="Запуск анализа",
    )
    object_type = models.CharField(max_length=128, blank=True, verbose_name="Тип объекта")
    object_id = models.CharField(max_length=128, blank=True, verbose_name="ID объекта")
    context_json = models.JSONField(null=True, blank=True, verbose_name="JSON-контекст")
    traceback_text = models.TextField(blank=True, verbose_name="Traceback")

    class Meta:
        """Мета-параметры модели технического журнала."""

        verbose_name = "Запись аудит-лога"
        verbose_name_plural = "Аудит-лог"
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["level", "created_at"], name="auditlog_level_created_idx"),
            models.Index(fields=["event_type", "created_at"], name="auditlog_event_created_idx"),
        ]

    def __str__(self) -> str:
        """Возвращает короткое представление записи журнала.

        Контекст использования:
            Применяется в административных списках и отладочных выводах.

        Параметры:
            Параметры отсутствуют.

        Возвращаемое значение:
            Строка с уровнем и типом события.

        Исключения и особые случаи:
            Исключения не ожидаются.

        Побочные эффекты:
            Побочные эффекты отсутствуют.
        """

        return f"{self.level} / {self.event_type}"
