"""Формы внутренней административной панели для CRUD контентных сущностей."""

from django import forms

from apps.accounts.models import User, UserRole
from apps.content.models import (
    AnalysisPrompt,
    Game,
    Scenario,
    ScenarioMediaAsset,
    ScenarioPrompt,
    SystemPrompt,
)


class BackofficeBaseForm(forms.ModelForm):
    """Базовая форма бэкофиса с контекстом текущего пользователя.

    Контекст использования:
        Используется во всех формах раздела контента для фильтрации доступных
        связанных объектов с учётом роли и владения.

    Параметры:
        user: Авторизованный пользователь, выполняющий операцию.

    Возвращаемое значение:
        Экземпляр формы с подготовленными queryset для связанных полей.

    Исключения и особые случаи:
        При отсутствии пользователя форма не применяет ролевые фильтры.

    Побочные эффекты:
        Побочные эффекты отсутствуют.
    """

    def __init__(self, *args, user: User | None = None, **kwargs):
        """Сохраняет текущего пользователя и инициализирует базовую форму.

        Контекст использования:
            Вызывается view-слоем для проброса ``request.user`` в форму.

        Параметры:
            *args: Позиционные аргументы базовой ``ModelForm``.
            user: Пользователь, выполняющий действие.
            **kwargs: Именованные аргументы базовой ``ModelForm``.

        Возвращаемое значение:
            Экземпляр инициализированной формы.

        Исключения и особые случаи:
            Исключения не ожидаются.

        Побочные эффекты:
            Сохраняет пользователя в ``self.user``.
        """

        super().__init__(*args, **kwargs)
        self.user = user


class GameForm(BackofficeBaseForm):
    """Форма создания и редактирования игры в бэкофисе."""

    class Meta:
        """Метаданные формы игры."""

        model = Game
        fields = ["slug", "title", "short_description", "sort_order", "is_published"]


class ScenarioForm(BackofficeBaseForm):
    """Форма создания и редактирования сценария в бэкофисе."""

    class Meta:
        """Метаданные формы сценария."""

        model = Scenario
        fields = [
            "game",
            "slug",
            "title",
            "short_description",
            "conditions_text",
            "opening_message_text",
            "media_asset",
            "sort_order",
            "is_published",
        ]

    def __init__(self, *args, user: User | None = None, **kwargs):
        """Ограничивает список игр и медиа по правам текущего пользователя.

        Контекст использования:
            Нужен, чтобы администратор видел только свои объекты при создании
            или редактировании сценариев.

        Параметры:
            *args: Позиционные аргументы базовой формы.
            user: Текущий пользователь бэкофиса.
            **kwargs: Именованные аргументы базовой формы.

        Возвращаемое значение:
            Инициализированная форма с отфильтрованными queryset.

        Исключения и особые случаи:
            Супер-администратор получает полный набор доступных объектов.

        Побочные эффекты:
            Побочные эффекты отсутствуют.
        """

        super().__init__(*args, user=user, **kwargs)
        if user and user.role == UserRole.ADMIN:
            self.fields["game"].queryset = Game.objects.filter(created_by=user)
            self.fields["media_asset"].queryset = ScenarioMediaAsset.objects.filter(uploaded_by=user)


class ScenarioPromptForm(BackofficeBaseForm):
    """Форма управления игровыми промтами сценария."""

    class Meta:
        """Метаданные формы игрового промта."""

        model = ScenarioPrompt
        fields = ["scenario", "title", "prompt_text", "is_active"]

    def __init__(self, *args, user: User | None = None, **kwargs):
        """Ограничивает выбор сценариев по правилам владения.

        Контекст использования:
            Предотвращает создание промта к чужому сценарию обычным админом.

        Параметры:
            *args: Позиционные аргументы базовой формы.
            user: Текущий пользователь бэкофиса.
            **kwargs: Именованные аргументы базовой формы.

        Возвращаемое значение:
            Инициализированная форма игрового промта.

        Исключения и особые случаи:
            Супер-администратор видит все сценарии.

        Побочные эффекты:
            Побочные эффекты отсутствуют.
        """

        super().__init__(*args, user=user, **kwargs)
        if user and user.role == UserRole.ADMIN:
            self.fields["scenario"].queryset = Scenario.objects.filter(created_by=user)


class AnalysisPromptForm(BackofficeBaseForm):
    """Форма управления аналитическими промтами игры."""

    class Meta:
        """Метаданные формы аналитического промта."""

        model = AnalysisPrompt
        fields = [
            "game",
            "alias",
            "title",
            "header_text",
            "comment_text",
            "prompt_text",
            "sort_order",
            "min_rating",
            "max_rating",
            "is_active",
        ]

    def __init__(self, *args, user: User | None = None, **kwargs):
        """Ограничивает выбор игры по правам пользователя.

        Контекст использования:
            Администратор может назначать аналитические промты только своим играм.

        Параметры:
            *args: Позиционные аргументы базовой формы.
            user: Текущий пользователь.
            **kwargs: Именованные аргументы базовой формы.

        Возвращаемое значение:
            Инициализированная форма аналитического промта.

        Исключения и особые случаи:
            Супер-администратор получает полный queryset игр.

        Побочные эффекты:
            Побочные эффекты отсутствуют.
        """

        super().__init__(*args, user=user, **kwargs)
        if user and user.role == UserRole.ADMIN:
            self.fields["game"].queryset = Game.objects.filter(created_by=user)


class SystemPromptForm(BackofficeBaseForm):
    """Форма управления системными промтами в бэкофисе."""

    class Meta:
        """Метаданные формы системного промта."""

        model = SystemPrompt
        fields = ["key", "title", "prompt_text", "is_active"]


class ScenarioMediaAssetForm(BackofficeBaseForm):
    """Форма управления медиа-ресурсом сценария."""

    class Meta:
        """Метаданные формы медиа-ресурса."""

        model = ScenarioMediaAsset
        fields = [
            "title",
            "file",
            "original_filename",
            "mime_type",
            "file_size_bytes",
            "checksum_sha256",
            "previous_version",
        ]

    def __init__(self, *args, user: User | None = None, **kwargs):
        """Ограничивает выбор предыдущих версий для обычного администратора.

        Контекст использования:
            Нужен для соблюдения владения медиа-объектами в контурной админке.

        Параметры:
            *args: Позиционные аргументы базовой формы.
            user: Текущий пользователь.
            **kwargs: Именованные аргументы базовой формы.

        Возвращаемое значение:
            Инициализированная форма медиа-ресурса.

        Исключения и особые случаи:
            Для супер-администратора фильтрация не применяется.

        Побочные эффекты:
            Побочные эффекты отсутствуют.
        """

        super().__init__(*args, user=user, **kwargs)
        if user and user.role == UserRole.ADMIN:
            self.fields["previous_version"].queryset = ScenarioMediaAsset.objects.filter(
                uploaded_by=user
            )


class UserCreateForm(forms.Form):
    """Форма создания пользователя супер-администратором в бэкофисе.

    Контекст использования:
        Применяется в отдельном разделе управления пользователями, доступном
        только роли ``superadmin`` для ручного заведения учётных записей.

    Параметры:
        Принимает email, nickname, пароль, роль и признак активности.

    Возвращаемое значение:
        Валидированные данные для создания ``accounts.User``.

    Исключения и особые случаи:
        Проверяет совпадение двух полей пароля и уникальность email.

    Побочные эффекты:
        В методе ``save`` создаёт нового пользователя в БД.
    """

    email = forms.EmailField(label="Email")
    nickname = forms.CharField(max_length=150, label="Никнейм")
    role = forms.ChoiceField(choices=UserRole.choices, label="Роль")
    is_active = forms.BooleanField(required=False, initial=True, label="Активен")
    password1 = forms.CharField(widget=forms.PasswordInput, label="Пароль")
    password2 = forms.CharField(widget=forms.PasswordInput, label="Пароль ещё раз")

    def clean_email(self) -> str:
        """Проверяет уникальность email для новой учётной записи.

        Контекст использования:
            Вызывается при валидации формы перед созданием пользователя.

        Параметры:
            Параметры отсутствуют.

        Возвращаемое значение:
            Нормализованный email из формы.

        Исключения и особые случаи:
            Бросает ``ValidationError``, если email уже занят.

        Побочные эффекты:
            Выполняет запрос в БД.
        """

        email = self.cleaned_data["email"]
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError("Пользователь с таким email уже существует.")
        return email

    def clean(self) -> dict:
        """Проверяет совпадение полей пароля перед созданием пользователя.

        Контекст использования:
            Нужен для защиты от случайного ввода разных паролей оператором.

        Параметры:
            Параметры отсутствуют.

        Возвращаемое значение:
            Словарь очищенных данных формы.

        Исключения и особые случаи:
            Добавляет ошибку формы при несовпадении паролей.

        Побочные эффекты:
            Побочные эффекты отсутствуют.
        """

        cleaned_data = super().clean()
        password1 = cleaned_data.get("password1")
        password2 = cleaned_data.get("password2")
        if password1 and password2 and password1 != password2:
            self.add_error("password2", "Пароли не совпадают.")
        return cleaned_data

    def save(self) -> User:
        """Создаёт пользователя с выбранной ролью и статусом активности.

        Контекст использования:
            Вызывается из view после успешной валидации формы.

        Параметры:
            Параметры отсутствуют.

        Возвращаемое значение:
            Созданный объект ``User``.

        Исключения и особые случаи:
            Ошибки модели могут возникнуть на уровне ``create_user``.

        Побочные эффекты:
            Создаёт новую запись пользователя в БД.
        """

        role = self.cleaned_data["role"]
        user = User.objects.create_user(
            email=self.cleaned_data["email"],
            nickname=self.cleaned_data["nickname"],
            password=self.cleaned_data["password1"],
            role=role,
            is_active=self.cleaned_data["is_active"],
            is_staff=role in {UserRole.ADMIN, UserRole.SUPERADMIN},
            is_superuser=role == UserRole.SUPERADMIN,
        )
        return user
