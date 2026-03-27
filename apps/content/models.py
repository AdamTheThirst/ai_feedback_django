"""Контентные модели игр, сценариев, медиа и промтов."""

from django.db import models
from django.db.models import Q

from apps.core.models import ArchivableModel, OwnedModel, TimestampedModel, UUIDPublicIdModel


class Game(UUIDPublicIdModel, TimestampedModel, ArchivableModel, OwnedModel):
    """Хранит игру как верхний контейнер сценариев и аналитических критериев.

    Контекст использования:
        Используется в пользовательском выборе тренажёра и в административном
        управлении набором сценариев и аналитических промтов.

    Параметры:
        Инициализируется стандартным способом через Django ORM.

    Возвращаемое значение:
        Экземпляр игры с настройками публикации и порядка отображения.

    Исключения и особые случаи:
        Нарушение уникальности ``slug`` приводит к ошибке целостности БД.

    Побочные эффекты:
        Служит родительской сущностью для сценариев и аналитических промтов.
    """

    slug = models.SlugField(unique=True, verbose_name="Slug")
    title = models.CharField(max_length=255, verbose_name="Название")
    short_description = models.TextField(blank=True, verbose_name="Краткое описание")
    sort_order = models.PositiveIntegerField(default=0, verbose_name="Порядок")
    is_published = models.BooleanField(default=False, verbose_name="Опубликована")

    class Meta:
        """Мета-параметры модели игры."""

        verbose_name = "Игра"
        verbose_name_plural = "Игры"
        ordering = ["sort_order", "title"]

    def __str__(self) -> str:
        """Возвращает название игры для человекочитаемого вывода.

        Контекст использования:
            Применяется в административных формах и отладочном выводе.

        Параметры:
            Параметры отсутствуют.

        Возвращаемое значение:
            Название игры.

        Исключения и особые случаи:
            Исключения не ожидаются при валидном экземпляре.

        Побочные эффекты:
            Побочные эффекты отсутствуют.
        """

        return self.title


class Scenario(UUIDPublicIdModel, TimestampedModel, ArchivableModel, OwnedModel):
    """Описывает конкретный сценарий внутри выбранной игры.

    Контекст использования:
        Используется для запуска диалога, отображения условий и начальной реплики
        персонажа в рамках выбранной игры.

    Параметры:
        Инициализируется через ORM с обязательной ссылкой на ``Game``.

    Возвращаемое значение:
        Экземпляр сценария с контентом и параметрами публикации.

    Исключения и особые случаи:
        Нарушение уникальности пары ``(game, slug)`` вызывает ошибку БД.

    Побочные эффекты:
        Является владельцем игровых промтов и используется в диалоговых сессиях.
    """

    game = models.ForeignKey(
        "content.Game",
        on_delete=models.CASCADE,
        related_name="scenarios",
        verbose_name="Игра",
    )
    slug = models.SlugField(verbose_name="Slug")
    title = models.CharField(max_length=255, verbose_name="Название")
    short_description = models.TextField(blank=True, verbose_name="Краткое описание")
    conditions_text = models.TextField(verbose_name="Условия сценария")
    opening_message_text = models.TextField(verbose_name="Стартовая реплика")
    media_asset = models.ForeignKey(
        "content.ScenarioMediaAsset",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="scenarios",
        verbose_name="Медиа-ресурс",
    )
    sort_order = models.PositiveIntegerField(default=0, verbose_name="Порядок")
    is_published = models.BooleanField(default=False, verbose_name="Опубликован")

    class Meta:
        """Мета-параметры модели сценария."""

        verbose_name = "Сценарий"
        verbose_name_plural = "Сценарии"
        ordering = ["game__sort_order", "sort_order", "title"]
        constraints = [
            models.UniqueConstraint(
                fields=["game", "slug"],
                name="content_scenario_unique_game_slug",
            ),
        ]

    def __str__(self) -> str:
        """Возвращает краткое строковое описание сценария.

        Контекст использования:
            Нужен для списков в админке и отладочного вывода.

        Параметры:
            Параметры отсутствуют.

        Возвращаемое значение:
            Строка ``<игра>: <сценарий>``.

        Исключения и особые случаи:
            Исключения не ожидаются.

        Побочные эффекты:
            Побочные эффекты отсутствуют.
        """

        return f"{self.game.title}: {self.title}"


class ScenarioMediaAsset(UUIDPublicIdModel, TimestampedModel, ArchivableModel):
    """Хранит медиа-ресурс сценария с поддержкой версий и архивирования.

    Контекст использования:
        Применяется для изображений и файлов, которые могут переиспользоваться
        в нескольких сценариях без физического дублирования.

    Параметры:
        Инициализируется через ORM при загрузке файла администратором.

    Возвращаемое значение:
        Экземпляр медиа-ресурса с метаданными файла.

    Исключения и особые случаи:
        Отсутствие файла нарушит обязательность поля ``file``.

    Побочные эффекты:
        Может участвовать в цепочке версий через ``previous_version``.
    """

    title = models.CharField(max_length=255, verbose_name="Название")
    file = models.FileField(upload_to="scenario_media/", verbose_name="Файл")
    original_filename = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Исходное имя файла",
    )
    mime_type = models.CharField(max_length=255, blank=True, verbose_name="MIME-тип")
    file_size_bytes = models.BigIntegerField(null=True, blank=True, verbose_name="Размер")
    checksum_sha256 = models.CharField(
        max_length=64,
        blank=True,
        verbose_name="SHA256",
    )
    previous_version = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="next_versions",
        verbose_name="Предыдущая версия",
    )
    uploaded_by = models.ForeignKey(
        "accounts.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="uploaded_media_assets",
        verbose_name="Кем загружено",
    )

    class Meta:
        """Мета-параметры модели медиа-ресурса."""

        verbose_name = "Медиа-ресурс сценария"
        verbose_name_plural = "Медиа-ресурсы сценариев"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        """Возвращает заголовок медиа-ресурса для админских списков.

        Контекст использования:
            Используется в административных списках и диагностике.

        Параметры:
            Параметры отсутствуют.

        Возвращаемое значение:
            Название ресурса.

        Исключения и особые случаи:
            Исключения не ожидаются.

        Побочные эффекты:
            Побочные эффекты отсутствуют.
        """

        return self.title


class ScenarioPrompt(UUIDPublicIdModel, TimestampedModel, ArchivableModel, OwnedModel):
    """Хранит версию игрового промта для конкретного сценария.

    Контекст использования:
        Используется игровым рантаймом для ролевого поведения ИИ и хранит
        историю изменений промтов через архивирование и признак активности.

    Параметры:
        Инициализируется через ORM с обязательной ссылкой на ``Scenario``.

    Возвращаемое значение:
        Экземпляр игрового промта конкретного сценария.

    Исключения и особые случаи:
        Наличие двух активных промтов на один сценарий запрещено ограничением.

    Побочные эффекты:
        Используется в снимке ``DialogSession.scenario_prompt_used``.
    """

    scenario = models.ForeignKey(
        "content.Scenario",
        on_delete=models.CASCADE,
        related_name="scenario_prompts",
        verbose_name="Сценарий",
    )
    title = models.CharField(max_length=255, verbose_name="Название версии")
    prompt_text = models.TextField(verbose_name="Текст игрового промта")
    is_active = models.BooleanField(default=True, verbose_name="Активен")

    class Meta:
        """Мета-параметры модели игрового промта."""

        verbose_name = "Игровой промт сценария"
        verbose_name_plural = "Игровые промты сценариев"
        ordering = ["scenario", "-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["scenario"],
                condition=Q(is_active=True),
                name="content_scenario_prompt_single_active_per_scenario",
            ),
        ]

    def __str__(self) -> str:
        """Возвращает представление промта с привязкой к сценарию.

        Контекст использования:
            Применяется для удобства выбора версии в админских интерфейсах.

        Параметры:
            Параметры отсутствуют.

        Возвращаемое значение:
            Строка ``<сценарий> / <название версии>``.

        Исключения и особые случаи:
            Исключения не ожидаются.

        Побочные эффекты:
            Побочные эффекты отсутствуют.
        """

        return f"{self.scenario.title} / {self.title}"


class AnalysisPrompt(UUIDPublicIdModel, TimestampedModel, ArchivableModel, OwnedModel):
    """Хранит аналитический критерий игры для оценки диалога.

    Контекст использования:
        Используется модулем анализа для последовательного запуска критериев
        и сохранения результатов по каждому активному промту.

    Параметры:
        Инициализируется через ORM с обязательной ссылкой на ``Game``.

    Возвращаемое значение:
        Экземпляр аналитического промта с границами шкалы оценки.

    Исключения и особые случаи:
        Проверка ``min_rating <= max_rating`` обеспечивается check-ограничением.

    Побочные эффекты:
        Участвует в расчёте динамической суммы результата ``N из M``.
    """

    game = models.ForeignKey(
        "content.Game",
        on_delete=models.CASCADE,
        related_name="analysis_prompts",
        verbose_name="Игра",
    )
    alias = models.SlugField(verbose_name="Alias")
    title = models.CharField(max_length=255, verbose_name="Название")
    header_text = models.CharField(max_length=255, verbose_name="Заголовок карточки")
    comment_text = models.TextField(blank=True, verbose_name="Комментарий")
    prompt_text = models.TextField(verbose_name="Текст аналитического промта")
    sort_order = models.PositiveIntegerField(default=0, verbose_name="Порядок")
    min_rating = models.SmallIntegerField(default=0, verbose_name="Минимальный балл")
    max_rating = models.SmallIntegerField(default=5, verbose_name="Максимальный балл")
    is_active = models.BooleanField(default=True, verbose_name="Активен")

    class Meta:
        """Мета-параметры модели аналитического промта."""

        verbose_name = "Аналитический промт"
        verbose_name_plural = "Аналитические промты"
        ordering = ["game", "sort_order", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["game", "alias"],
                name="content_analysis_prompt_unique_game_alias",
            ),
            models.UniqueConstraint(
                fields=["game", "sort_order"],
                name="content_analysis_prompt_unique_game_sort_order",
            ),
            models.CheckConstraint(
                check=Q(min_rating__lte=models.F("max_rating")),
                name="content_analysis_prompt_min_lte_max",
            ),
        ]
        indexes = [
            models.Index(fields=["game", "sort_order", "is_active"], name="cnt_ap_game_sort_act_idx"),
        ]

    def __str__(self) -> str:
        """Возвращает краткое отображение аналитического критерия.

        Контекст использования:
            Отображается в списках админки и связях с результатами анализа.

        Параметры:
            Параметры отсутствуют.

        Возвращаемое значение:
            Строка ``<игра>: <title>``.

        Исключения и особые случаи:
            Исключения не ожидаются.

        Побочные эффекты:
            Побочные эффекты отсутствуют.
        """

        return f"{self.game.title}: {self.title}"


class SystemPrompt(UUIDPublicIdModel, TimestampedModel, ArchivableModel, OwnedModel):
    """Хранит системные служебные промты платформы по уникальному ключу.

    Контекст использования:
        Применяется для служебных задач, например генерации метаданных
        аналитических критериев, отдельно от игровых и аналитических промтов.

    Параметры:
        Инициализируется через ORM с ключом и текстом системного промта.

    Возвращаемое значение:
        Экземпляр системного промта.

    Исключения и особые случаи:
        Для одного ``key`` допускается только одна активная запись.

    Побочные эффекты:
        Используется сервисами платформы при специальных служебных операциях.
    """

    key = models.SlugField(verbose_name="Ключ")
    title = models.CharField(max_length=255, verbose_name="Название")
    prompt_text = models.TextField(verbose_name="Текст системного промта")
    is_active = models.BooleanField(default=True, verbose_name="Активен")

    class Meta:
        """Мета-параметры модели системного промта."""

        verbose_name = "Системный промт"
        verbose_name_plural = "Системные промты"
        ordering = ["key", "-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["key", "is_active"], name="content_system_prompt_key_active_unique"),
        ]

    def __str__(self) -> str:
        """Возвращает краткое представление системного промта.

        Контекст использования:
            Используется в административных списках и связанной диагностике.

        Параметры:
            Параметры отсутствуют.

        Возвращаемое значение:
            Строка ``<key>: <title>``.

        Исключения и особые случаи:
            Исключения не ожидаются.

        Побочные эффекты:
            Побочные эффекты отсутствуют.
        """

        return f"{self.key}: {self.title}"
