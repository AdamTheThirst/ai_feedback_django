"""Модели запуска анализа и результатов по аналитическим критериям."""

from django.db import models
from django.db.models import Q

from apps.core.models import TimestampedModel, UUIDPublicIdModel


class AnalysisRunStatus(models.TextChoices):
    """Определяет статусы выполнения анализа диалога.

    Контекст использования:
        Применяется в ``AnalysisRun.status`` для хранения жизненного цикла
        процесса анализа от постановки до завершения или ошибки.

    Параметры:
        Параметры отсутствуют.

    Возвращаемое значение:
        Строковые коды статусов анализа.

    Исключения и особые случаи:
        Особые исключения отсутствуют.

    Побочные эффекты:
        Побочные эффекты отсутствуют.
    """

    PENDING = "pending", "Ожидает"
    RUNNING = "running", "Выполняется"
    COMPLETED = "completed", "Завершён"
    FAILED = "failed", "Ошибка"
    SKIPPED = "skipped", "Пропущен"


class AnalysisValidationStatus(models.TextChoices):
    """Хранит статусы валидации ответа LLM по отдельному критерию.

    Контекст использования:
        Применяется в ``AnalysisResult.validation_status`` для различения
        корректного результата и сценариев ошибок парсинга/схемы.

    Параметры:
        Параметры отсутствуют.

    Возвращаемое значение:
        Строковые коды валидации результата.

    Исключения и особые случаи:
        Особые исключения отсутствуют.

    Побочные эффекты:
        Побочные эффекты отсутствуют.
    """

    VALID = "valid", "Валидно"
    INVALID_JSON = "invalid_json", "Невалидный JSON"
    INVALID_SCHEMA = "invalid_schema", "Невалидная схема"
    FALLBACK_SAVED = "fallback_saved", "Сохранён fallback"


class AnalysisRun(UUIDPublicIdModel, TimestampedModel):
    """Фиксирует факт и технический статус запуска анализа диалога.

    Контекст использования:
        Отделяет жизненный цикл анализа от жизненного цикла диалога и позволяет
        сохранять техническую информацию о попытках и ошибках анализа.

    Параметры:
        Создаётся ORM со ссылкой ``dialog`` один-к-одному.

    Возвращаемое значение:
        Экземпляр запуска анализа для выбранного диалога.

    Исключения и особые случаи:
        Нарушение уникальности ``dialog`` невозможно из-за ``OneToOneField``.

    Побочные эффекты:
        Служит контейнером для дочерних ``AnalysisResult``.
    """

    dialog = models.OneToOneField(
        "dialogs.DialogSession",
        on_delete=models.CASCADE,
        related_name="analysis_run",
        verbose_name="Диалог",
    )
    status = models.CharField(
        max_length=32,
        choices=AnalysisRunStatus.choices,
        default=AnalysisRunStatus.PENDING,
        verbose_name="Статус",
    )
    started_at = models.DateTimeField(verbose_name="Запущен")
    finished_at = models.DateTimeField(null=True, blank=True, verbose_name="Завершён")
    llm_attempt_count = models.PositiveIntegerField(default=0, verbose_name="Количество LLM-попыток")
    error_code = models.CharField(max_length=128, blank=True, verbose_name="Код ошибки")
    error_message = models.TextField(blank=True, verbose_name="Текст ошибки")

    class Meta:
        """Мета-параметры модели запуска анализа."""

        verbose_name = "Запуск анализа"
        verbose_name_plural = "Запуски анализа"
        ordering = ["-started_at"]

    def __str__(self) -> str:
        """Возвращает краткое представление запуска анализа.

        Контекст использования:
            Используется в админке и диагностических выводах.

        Параметры:
            Параметры отсутствуют.

        Возвращаемое значение:
            Строка с публичным ID диалога и статусом анализа.

        Исключения и особые случаи:
            Исключения не ожидаются.

        Побочные эффекты:
            Побочные эффекты отсутствуют.
        """

        return f"{self.dialog.public_id} / {self.status}"


class AnalysisResult(TimestampedModel):
    """Сохраняет результат одного аналитического критерия в рамках запуска анализа.

    Контекст использования:
        Используется для отображения карточек анализа и расчёта итоговой суммы
        баллов по всем активным критериям выбранной игры.

    Параметры:
        Создаётся ORM с обязательными ссылками на ``AnalysisRun`` и ``AnalysisPrompt``.

    Возвращаемое значение:
        Экземпляр результата по одному критерию.

    Исключения и особые случаи:
        Ограничения контролируют уникальность критерия в рамках одного запуска
        и диапазон ``rating`` между ``rating_min`` и ``rating_max``.

    Побочные эффекты:
        При удалении ``AnalysisRun`` соответствующие результаты удаляются каскадно.
    """

    analysis_run = models.ForeignKey(
        "analysis.AnalysisRun",
        on_delete=models.CASCADE,
        related_name="results",
        verbose_name="Запуск анализа",
    )
    analysis_prompt = models.ForeignKey(
        "content.AnalysisPrompt",
        on_delete=models.PROTECT,
        related_name="analysis_results",
        verbose_name="Аналитический промт",
    )
    sort_order_snapshot = models.PositiveIntegerField(verbose_name="Порядок (snapshot)")
    alias_snapshot = models.SlugField(verbose_name="Alias (snapshot)")
    title_snapshot = models.CharField(max_length=255, verbose_name="Название (snapshot)")
    header_snapshot_text = models.CharField(max_length=255, verbose_name="Заголовок (snapshot)")
    comment_snapshot_text = models.TextField(blank=True, verbose_name="Комментарий (snapshot)")
    rating = models.SmallIntegerField(verbose_name="Балл")
    rating_min = models.SmallIntegerField(verbose_name="Минимум шкалы")
    rating_max = models.SmallIntegerField(verbose_name="Максимум шкалы")
    analysis_text = models.TextField(verbose_name="Текст анализа")
    raw_llm_response_text = models.TextField(blank=True, verbose_name="Сырой ответ LLM")
    parsed_json_snapshot = models.JSONField(null=True, blank=True, verbose_name="JSON snapshot")
    validation_status = models.CharField(
        max_length=32,
        choices=AnalysisValidationStatus.choices,
        default=AnalysisValidationStatus.VALID,
        verbose_name="Статус валидации",
    )
    validation_error_message = models.TextField(blank=True, verbose_name="Ошибка валидации")
    llm_attempt_count = models.PositiveIntegerField(default=1, verbose_name="Попыток по критерию")

    class Meta:
        """Мета-параметры модели результата анализа."""

        verbose_name = "Результат анализа"
        verbose_name_plural = "Результаты анализа"
        ordering = ["analysis_run", "sort_order_snapshot", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["analysis_run", "analysis_prompt"],
                name="analysis_result_unique_run_prompt",
            ),
            models.CheckConstraint(
                check=Q(rating__gte=models.F("rating_min"))
                & Q(rating__lte=models.F("rating_max")),
                name="analysis_result_rating_in_range",
            ),
        ]
        indexes = [
            models.Index(fields=["analysis_run", "sort_order_snapshot"], name="analysis_result_run_sort_idx"),
        ]

    def __str__(self) -> str:
        """Возвращает краткую строку результата по критерию.

        Контекст использования:
            Используется для удобства в админке и логах при просмотре записей.

        Параметры:
            Параметры отсутствуют.

        Возвращаемое значение:
            Строка с публичным ID диалога и alias критерия.

        Исключения и особые случаи:
            Исключения не ожидаются.

        Побочные эффекты:
            Побочные эффекты отсутствуют.
        """

        return f"{self.analysis_run.dialog.public_id} / {self.alias_snapshot}"
