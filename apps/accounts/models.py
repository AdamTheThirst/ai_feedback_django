"""Модели пользователей, ролей и базовых атрибутов доступа."""

from django.contrib.auth.models import AbstractUser
from django.contrib.auth.models import UserManager as DjangoUserManager
from django.db import models
from django.db.models import Q

from apps.core.models import TimestampedModel, UUIDPublicIdModel


class UserRole(models.TextChoices):
    """Определяет допустимые роли пользователей в системе доступа.

    Контекст использования:
        Используется в поле ``User.role`` для строгого разграничения прав
        обычных пользователей, администраторов и супер-администраторов.

    Параметры:
        Параметры не принимает; содержит фиксированный набор констант.

    Возвращаемое значение:
        Строковые значения ролей для сохранения в базе данных.

    Исключения и особые случаи:
        Особые исключения отсутствуют.

    Побочные эффекты:
        Побочные эффекты отсутствуют.
    """

    USER = "user", "Пользователь"
    ADMIN = "admin", "Администратор"
    SUPERADMIN = "superadmin", "Супер-администратор"


class UserManager(DjangoUserManager):
    """Кастомный менеджер пользователя с email-логином без поля username.

    Контекст использования:
        Используется командой ``createsuperuser``, формами регистрации и
        тестами проекта, чтобы создание пользователя работало с ``email``
        как основным идентификатором вместо ``username``.

    Параметры:
        Наследует стандартные параметры менеджера Django.

    Возвращаемое значение:
        Возвращает экземпляры ``User`` при создании учетных записей.

    Исключения и особые случаи:
        При отсутствии email выбрасывает ``ValueError``.

    Побочные эффекты:
        Создаёт записи пользователей в БД с дефолтными avatar-полями,
        если они не были переданы явно.
    """

    use_in_migrations = True

    def _build_avatar_defaults(self, email: str, nickname: str) -> tuple[str, str]:
        """Строит fallback-значения для аватара при создании пользователя.

        Контекст использования:
            Применяется в ``create_user``/``create_superuser`` для сценариев,
            где avatar-поля не переданы (например интерактивный createsuperuser).

        Параметры:
            email: Email создаваемого пользователя.
            nickname: Никнейм создаваемого пользователя.

        Возвращаемое значение:
            Кортеж ``(avatar_letter, avatar_bg_hex)``.

        Исключения и особые случаи:
            Если nickname пустой, берётся первая буква email или ``U``.

        Побочные эффекты:
            Побочные эффекты отсутствуют.
        """

        seed = (nickname or "").strip() or (email or "").strip() or "U"
        return seed[0].upper(), "#D6E8FF"

    def _create_user(self, email: str, password: str | None, **extra_fields):
        """Создаёт пользователя в базе с нормализованным email и паролем.

        Контекст использования:
            Внутренний единый путь создания пользователя для обычных и
            суперпользователей с учётом custom-полей модели проекта.

        Параметры:
            email: Email как основной логин пользователя.
            password: Пароль пользователя.
            extra_fields: Дополнительные поля модели ``User``.

        Возвращаемое значение:
            Сохранённый экземпляр ``User``.

        Исключения и особые случаи:
            При пустом email выбрасывает ``ValueError``.

        Побочные эффекты:
            Выполняет запись пользователя в БД через ``save``.
        """

        if not email:
            raise ValueError("Email обязателен для создания пользователя.")

        email = self.normalize_email(email)
        nickname = extra_fields.get("nickname") or email.split("@")[0]
        avatar_letter = extra_fields.get("avatar_letter")
        avatar_bg_hex = extra_fields.get("avatar_bg_hex")
        if not avatar_letter or not avatar_bg_hex:
            default_letter, default_color = self._build_avatar_defaults(email=email, nickname=nickname)
            extra_fields.setdefault("avatar_letter", default_letter)
            extra_fields.setdefault("avatar_bg_hex", default_color)
        extra_fields.setdefault("nickname", nickname)

        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email: str, password: str | None = None, **extra_fields):
        """Создаёт обычного пользователя с базовыми флагами безопасности.

        Контекст использования:
            Вызывается регистрацией, тестами и seed-сценариями для создания
            стандартных учетных записей без административных прав.

        Параметры:
            email: Email пользователя.
            password: Пароль пользователя.
            extra_fields: Дополнительные поля ``User``.

        Возвращаемое значение:
            Сохранённый экземпляр ``User`` с ролью по умолчанию.

        Исключения и особые случаи:
            Ошибки валидации полей возникают на этапе сохранения модели.

        Побочные эффекты:
            Создаёт пользователя в БД.
        """

        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(email=email, password=password, **extra_fields)

    def create_superuser(self, email: str, password: str | None = None, **extra_fields):
        """Создаёт суперпользователя, совместимого с Django createsuperuser.

        Контекст использования:
            Используется management-командой ``createsuperuser`` и должен
            принимать ``email`` без параметра ``username``.

        Параметры:
            email: Email суперпользователя.
            password: Пароль суперпользователя.
            extra_fields: Дополнительные поля ``User``.

        Возвращаемое значение:
            Сохранённый суперпользователь ``User``.

        Исключения и особые случаи:
            Если `is_staff` или `is_superuser` переданы как ``False``,
            выбрасывает ``ValueError``.

        Побочные эффекты:
            Создаёт пользователя в БД с административными флагами.
        """

        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("role", UserRole.SUPERADMIN)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Суперпользователь должен иметь is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Суперпользователь должен иметь is_superuser=True.")

        return self._create_user(email=email, password=password, **extra_fields)


class User(UUIDPublicIdModel, TimestampedModel, AbstractUser):
    """Кастомная модель пользователя с email-логином и ролевой иерархией.

    Контекст использования:
        Является центральной моделью аутентификации и авторизации проекта,
        расширяя стандартного пользователя Django полями никнейма, роли и аватара.

    Параметры:
        Инициализируется стандартным механизмом ORM Django.

    Возвращаемое значение:
        Экземпляр пользователя для сценариев входа, доступа и владения сущностями.

    Исключения и особые случаи:
        При нарушении ограничений уникальности или check-констрейнтов БД
        может возникать ``IntegrityError`` на уровне транзакции.

    Побочные эффекты:
        Используется как источник FK-ссылок для большинства предметных моделей.
    """

    username = None
    email = models.EmailField(unique=True, verbose_name="Email")
    nickname = models.CharField(max_length=150, verbose_name="Никнейм")
    role = models.CharField(
        max_length=32,
        choices=UserRole.choices,
        default=UserRole.USER,
        verbose_name="Роль",
    )
    is_primary_superadmin = models.BooleanField(
        default=False,
        verbose_name="Главный супер-администратор",
    )
    avatar_letter = models.CharField(max_length=1, verbose_name="Буква аватара")
    avatar_bg_hex = models.CharField(max_length=7, verbose_name="Цвет фона аватара")
    created_by = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_users",
        verbose_name="Кем создан",
    )

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS: list[str] = ["nickname"]
    objects = UserManager()

    class Meta:
        """Мета-параметры модели пользователя и ограничения целостности."""

        verbose_name = "Пользователь"
        verbose_name_plural = "Пользователи"
        constraints = [
            models.CheckConstraint(
                check=Q(is_primary_superadmin=False)
                | Q(role=UserRole.SUPERADMIN),
                name="accounts_user_primary_requires_superadmin_role",
            ),
            models.CheckConstraint(
                check=(Q(role=UserRole.USER, is_staff=False) | ~Q(role=UserRole.USER)),
                name="accounts_user_regular_not_staff",
            ),
            models.CheckConstraint(
                check=(Q(role=UserRole.USER) | Q(is_staff=True)),
                name="accounts_user_admin_roles_staff",
            ),
            models.UniqueConstraint(
                fields=["is_primary_superadmin"],
                condition=Q(is_primary_superadmin=True),
                name="accounts_user_single_primary_superadmin",
            ),
        ]

    @property
    def can_access_backoffice(self) -> bool:
        """Возвращает признак доступа пользователя к внутренней админ-панели.

        Контекст использования:
            Используется в шаблонах и сервисах для показа админской навигации
            только ролям администратора и супер-администратора.

        Параметры:
            Параметры отсутствуют.

        Возвращаемое значение:
            ``True`` для ролей ``admin`` и ``superadmin``.

        Исключения и особые случаи:
            Особые исключения отсутствуют.

        Побочные эффекты:
            Побочные эффекты отсутствуют.
        """

        return self.role in {UserRole.ADMIN, UserRole.SUPERADMIN}

    def __str__(self) -> str:
        """Возвращает человекочитаемое представление пользователя для админки.

        Контекст использования:
            Применяется в Django Admin, shell и журналах при выводе экземпляра.

        Параметры:
            Параметры отсутствуют.

        Возвращаемое значение:
            Строка вида ``nickname <email>``.

        Исключения и особые случаи:
            Исключения не ожидаются при валидных данных пользователя.

        Побочные эффекты:
            Побочные эффекты отсутствуют.
        """

        return f"{self.nickname} <{self.email}>"
