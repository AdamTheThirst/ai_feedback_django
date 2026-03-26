"""Модели пользователей, ролей и базовых атрибутов доступа."""

from django.contrib.auth.models import AbstractUser
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
