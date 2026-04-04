"""Модели глобальных платформенных настроек и редактируемых UI-текстов."""

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q

from apps.core.models import ArchivableModel, TimestampedModel


class PlatformSettings(TimestampedModel):
    """Хранит глобальные технические настройки платформы в singleton-формате.

    Контекст использования:
        Используется сервисами запуска диалога и анализа как источник базовых
        лимитов таймера, ограничений сообщений и параметров LLM-вызовов.

    Параметры:
        Инициализируется через ORM; должна существовать одна активная запись.

    Возвращаемое значение:
        Экземпляр глобальных параметров платформы.

    Исключения и особые случаи:
        Нарушение ограничений min/max или множественной активной записи приводит
        к ошибке валидации или целостности данных.

    Побочные эффекты:
        Изменения влияют на новые диалоги, но не на уже созданные snapshot-сессии.
    """

    is_active = models.BooleanField(default=True, verbose_name="Активна")
    default_dialog_duration_minutes = models.PositiveSmallIntegerField(
        default=10,
        validators=[MinValueValidator(1), MaxValueValidator(120)],
        help_text="Глобальная длительность диалога в минутах.",
        verbose_name="Длительность диалога по умолчанию (мин)",
    )
    user_timer_min_minutes = models.PositiveSmallIntegerField(
        default=5,
        validators=[MinValueValidator(1), MaxValueValidator(120)],
        help_text="Нижняя граница будущей пользовательской настройки таймера.",
        verbose_name="Минимум пользовательского таймера (мин)",
    )
    user_timer_max_minutes = models.PositiveSmallIntegerField(
        default=20,
        validators=[MinValueValidator(1), MaxValueValidator(120)],
        help_text="Верхняя граница будущей пользовательской настройки таймера.",
        verbose_name="Максимум пользовательского таймера (мин)",
    )
    default_show_timer = models.BooleanField(default=True, verbose_name="Показывать таймер")
    max_user_message_chars = models.PositiveIntegerField(
        default=2500,
        validators=[MinValueValidator(1), MaxValueValidator(20000)],
        help_text="Лимит длины пользовательского сообщения.",
        verbose_name="Лимит сообщения пользователя",
    )
    max_game_reply_chars = models.PositiveIntegerField(
        default=3500,
        validators=[MinValueValidator(1), MaxValueValidator(20000)],
        help_text="Лимит длины игрового ответа ассистента.",
        verbose_name="Лимит игрового ответа",
    )
    max_analysis_reply_chars = models.PositiveIntegerField(
        default=4500,
        validators=[MinValueValidator(1), MaxValueValidator(30000)],
        help_text="Лимит длины аналитического ответа.",
        verbose_name="Лимит аналитического ответа",
    )
    llm_base_url = models.URLField(verbose_name="LLM base URL")
    llm_api_key = models.CharField(max_length=255, blank=True, verbose_name="LLM API ключ")
    llm_model_name = models.CharField(max_length=255, default="Qwen/Qwen3-32B", verbose_name="LLM модель")
    llm_temperature = models.DecimalField(
        max_digits=3,
        decimal_places=2,
        default=0.70,
        validators=[MinValueValidator(0), MaxValueValidator(2)],
        verbose_name="LLM temperature",
    )
    llm_top_p = models.DecimalField(
        max_digits=3,
        decimal_places=2,
        default=0.80,
        validators=[MinValueValidator(0), MaxValueValidator(1)],
        verbose_name="LLM top-p",
    )
    llm_game_max_tokens = models.PositiveIntegerField(
        default=1500,
        validators=[MinValueValidator(1), MaxValueValidator(32768)],
        verbose_name="Max tokens (игра)",
    )
    llm_analysis_max_tokens = models.PositiveIntegerField(
        default=2500,
        validators=[MinValueValidator(1), MaxValueValidator(32768)],
        verbose_name="Max tokens (анализ)",
    )
    client_abort_grace_seconds = models.PositiveSmallIntegerField(
        default=15,
        validators=[MinValueValidator(1), MaxValueValidator(600)],
        verbose_name="Окно ожидания после client abort (сек)",
    )

    class Meta:
        """Мета-параметры модели глобальных настроек платформы."""

        verbose_name = "Глобальные настройки платформы"
        verbose_name_plural = "Глобальные настройки платформы"
        constraints = [
            models.UniqueConstraint(
                fields=["is_active"],
                condition=Q(is_active=True),
                name="platform_config_single_active_settings",
            ),
            models.CheckConstraint(
                check=Q(user_timer_min_minutes__lte=models.F("user_timer_max_minutes")),
                name="platform_config_timer_min_lte_max",
            ),
        ]

    def __str__(self) -> str:
        """Возвращает человекочитаемое имя активного/неактивного набора настроек.

        Контекст использования:
            Применяется в административных списках singleton-настроек.

        Параметры:
            Параметры отсутствуют.

        Возвращаемое значение:
            Строка с признаком активности и моделью LLM.

        Исключения и особые случаи:
            Исключения не ожидаются.

        Побочные эффекты:
            Побочные эффекты отсутствуют.
        """

        state = "активна" if self.is_active else "неактивна"
        return f"Настройки ({state}) / {self.llm_model_name}"


class UIText(TimestampedModel, ArchivableModel):
    """Хранит редактируемые тексты интерфейса по стабильным ключам.

    Контекст использования:
        Нужен для изменения UI-строк через админку без модификации шаблонов и кода.

    Параметры:
        Инициализируется через ORM с уникальным ``key`` и текстовым значением.

    Возвращаемое значение:
        Экземпляр UI-строки платформы.

    Исключения и особые случаи:
        Нарушение уникальности ``key`` приводит к ошибке целостности БД.

    Побочные эффекты:
        Новые отображения интерфейса используют обновлённое значение записи.
    """

    key = models.SlugField(unique=True, verbose_name="Ключ")
    title = models.CharField(max_length=255, verbose_name="Название")
    text_value = models.TextField(verbose_name="Текст")
    description = models.TextField(blank=True, verbose_name="Описание")
    updated_by = models.ForeignKey(
        "accounts.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="updated_ui_texts",
        verbose_name="Обновил",
    )

    class Meta:
        """Мета-параметры модели UI-текста."""

        verbose_name = "UI-текст"
        verbose_name_plural = "UI-тексты"
        ordering = ["key"]

    def __str__(self) -> str:
        """Возвращает ключ UI-текста для списков и диагностического вывода.

        Контекст использования:
            Используется в админке и в отладочных журналах.

        Параметры:
            Параметры отсутствуют.

        Возвращаемое значение:
            Строковое значение ключа ``key``.

        Исключения и особые случаи:
            Исключения не ожидаются.

        Побочные эффекты:
            Побочные эффекты отсутствуют.
        """

        return self.key
