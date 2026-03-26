"""Формы регистрации и входа пользователя для веб-части проекта."""

from django import forms
from django.contrib.auth import authenticate
from django.contrib.auth.forms import UserCreationForm

from apps.accounts.models import User
from apps.accounts.services.avatar import build_avatar_bg_hex, build_avatar_letter


class RegistrationForm(UserCreationForm):
    """Форма регистрации пользователя по email, никнейму и паролю.

    Контекст использования:
        Применяется на публичной странице регистрации для создания новой
        пользовательской учётной записи с базовыми профильными атрибутами.

    Параметры:
        Стандартные параметры Django Form передаются через ``__init__``.

    Возвращаемое значение:
        Валидированная форма создаёт экземпляр ``User`` при вызове ``save``.

    Исключения и особые случаи:
        Ошибки валидации email или пароля возвращаются как ошибки формы.

    Побочные эффекты:
        Заполняет поля аватара на основе никнейма и email пользователя.
    """

    class Meta(UserCreationForm.Meta):
        """Метаданные регистрационной формы пользователя."""

        model = User
        fields = ("email", "nickname", "password1", "password2")

    def save(self, commit: bool = True) -> User:
        """Создаёт пользователя и рассчитывает данные буквенного аватара.

        Контекст использования:
            Вызывается view регистрации после успешной валидации формы.

        Параметры:
            commit: Признак немедленного сохранения экземпляра в БД.

        Возвращаемое значение:
            Экземпляр ``User`` с заполненными обязательными полями профиля.

        Исключения и особые случаи:
            При ``commit=False`` возвращается несохранённый экземпляр модели.

        Побочные эффекты:
            При ``commit=True`` создаёт новую запись пользователя в БД.
        """

        user = super().save(commit=False)
        user.avatar_letter = build_avatar_letter(self.cleaned_data["nickname"])
        user.avatar_bg_hex = build_avatar_bg_hex(self.cleaned_data["email"])
        if commit:
            user.save()
        return user


class EmailAuthenticationForm(forms.Form):
    """Форма входа с email и паролем, адаптированная для кастомной модели.

    Контекст использования:
        Используется на странице входа для аутентификации через email как
        основной идентификатор пользователя.

    Параметры:
        Принимает ``request`` через ``__init__`` для передачи в ``authenticate``.

    Возвращаемое значение:
        Валидированная форма содержит найденного пользователя в ``self.user``.

    Исключения и особые случаи:
        При неверных данных возвращает ошибку валидации без раскрытия деталей.

    Побочные эффекты:
        Побочные эффекты отсутствуют.
    """

    email = forms.EmailField(label="Email")
    password = forms.CharField(label="Пароль", widget=forms.PasswordInput)

    error_messages = {
        "invalid_login": "Неверный email или пароль.",
        "inactive": "Учётная запись деактивирована.",
    }

    def __init__(self, request=None, *args, **kwargs):
        """Инициализирует форму входа и сохраняет ссылку на request.

        Контекст использования:
            Нужен для корректной работы backend-аутентификации Django.

        Параметры:
            request: Текущий HTTP-запрос.
            *args: Позиционные аргументы базового класса формы.
            **kwargs: Именованные аргументы базового класса формы.

        Возвращаемое значение:
            Экземпляр формы входа.

        Исключения и особые случаи:
            Особые исключения не предусмотрены.

        Побочные эффекты:
            Сохраняет request в атрибуте ``self.request``.
        """

        super().__init__(*args, **kwargs)
        self.request = request
        self.user = None

    def clean(self):
        """Выполняет аутентификацию пользователя по email и паролю.

        Контекст использования:
            Вызывается стандартным процессом валидации формы входа.

        Параметры:
            Параметры отсутствуют.

        Возвращаемое значение:
            Словарь очищенных данных формы.

        Исключения и особые случаи:
            Выбрасывает ``ValidationError`` при неверных данных входа.

        Побочные эффекты:
            Записывает найденного пользователя в ``self.user``.
        """

        cleaned_data = super().clean()
        email = cleaned_data.get("email")
        password = cleaned_data.get("password")

        if email and password:
            self.user = authenticate(self.request, email=email, password=password)
            if self.user is None:
                raise forms.ValidationError(self.error_messages["invalid_login"])
            if not self.user.is_active:
                raise forms.ValidationError(self.error_messages["inactive"])

        return cleaned_data

    def get_user(self) -> User | None:
        """Возвращает пользователя, найденного в процессе валидации формы.

        Контекст использования:
            Вызывается view входа после ``is_valid`` для выполнения ``login``.

        Параметры:
            Параметры отсутствуют.

        Возвращаемое значение:
            Экземпляр ``User`` или ``None``.

        Исключения и особые случаи:
            Если форма невалидна, как правило возвращается ``None``.

        Побочные эффекты:
            Побочные эффекты отсутствуют.
        """

        return self.user
