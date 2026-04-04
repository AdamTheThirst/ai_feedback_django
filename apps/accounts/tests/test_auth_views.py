"""Smoke-тесты сценариев регистрации, входа и выхода пользователя."""

from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import User, UserRole


class AuthViewsTests(TestCase):
    """Проверяет ключевые пользовательские сценарии аутентификации V1.

    Контекст использования:
        Гарантирует работоспособность базовых маршрутов регистрации/входа/выхода
        для следующего этапа реализации игрового и аналитического функционала.

    Параметры:
        Использует тестовый клиент Django и тестовую БД.

    Возвращаемое значение:
        Не возвращает значение; выполняет набор unit/smoke проверок.

    Исключения и особые случаи:
        Любое нарушение ожидаемого поведения приводит к падению теста.

    Побочные эффекты:
        Создаёт тестовые записи пользователей в транзакционной тестовой БД.
    """

    def test_register_creates_user_and_logs_in(self) -> None:
        """Проверяет успешную регистрацию и автоматическую авторизацию.

        Контекст использования:
            Покрывает основной пользовательский поток регистрации из спецификации.

        Параметры:
            Параметры отсутствуют.

        Возвращаемое значение:
            Ничего не возвращает.

        Исключения и особые случаи:
            При ошибке регистрации тест должен завершиться неуспешно.

        Побочные эффекты:
            Создаёт новую учётную запись в тестовой БД.
        """

        response = self.client.post(
            reverse("accounts:register"),
            data={
                "email": "new.user@example.com",
                "nickname": "Новый",
                "password1": "StrongPassword123",
                "password2": "StrongPassword123",
            },
        )

        self.assertRedirects(response, reverse("content:game_list"))
        created_user = User.objects.get(email="new.user@example.com")
        self.assertEqual(created_user.role, UserRole.USER)
        self.assertTrue(created_user.avatar_letter)

    def test_login_with_email_and_password(self) -> None:
        """Проверяет вход пользователя по email и паролю.

        Контекст использования:
            Подтверждает реализацию требования входа именно по email.

        Параметры:
            Параметры отсутствуют.

        Возвращаемое значение:
            Ничего не возвращает.

        Исключения и особые случаи:
            Невалидный логин должен остаться на странице входа.

        Побочные эффекты:
            Создаёт пользователя в тестовой БД для проверки аутентификации.
        """

        user = User.objects.create_user(
            email="login.user@example.com",
            nickname="Логин",
            password="StrongPassword123",
            avatar_letter="Л",
            avatar_bg_hex="#F7D6D0",
        )

        response = self.client.post(
            reverse("accounts:login"),
            data={"email": user.email, "password": "StrongPassword123"},
        )

        self.assertRedirects(response, reverse("content:game_list"))

    def test_logout_requires_post_and_redirects(self) -> None:
        """Проверяет выход по POST и редирект на публичный экран входа.

        Контекст использования:
            Подтверждает соответствие маршрута logout требованиям безопасности.

        Параметры:
            Параметры отсутствуют.

        Возвращаемое значение:
            Ничего не возвращает.

        Исключения и особые случаи:
            Исключения не ожидаются при корректной сессии.

        Побочные эффекты:
            Завершает авторизованную сессию тестового клиента.
        """

        user = User.objects.create_user(
            email="logout.user@example.com",
            nickname="Выход",
            password="StrongPassword123",
            avatar_letter="В",
            avatar_bg_hex="#F7D6D0",
        )
        self.client.force_login(user)

        response = self.client.post(reverse("accounts:logout"))

        self.assertRedirects(response, reverse("accounts:login"))

    def test_create_superuser_works_with_email_without_username(self) -> None:
        """Проверяет создание суперпользователя без параметра username.

        Контекст использования:
            Закрывает регрессию команды ``createsuperuser`` для кастомной
            модели пользователя с ``USERNAME_FIELD = email``.

        Параметры:
            Параметры отсутствуют.

        Возвращаемое значение:
            Ничего не возвращает; выполняет проверки флагов и роли.

        Исключения и особые случаи:
            При некорректной сигнатуре менеджера тест завершится ошибкой.

        Побочные эффекты:
            Создаёт суперпользователя в тестовой БД.
        """

        superuser = User.objects.create_superuser(
            email="super@example.com",
            nickname="Супер",
            password="StrongPassword123",
        )

        self.assertTrue(superuser.is_staff)
        self.assertTrue(superuser.is_superuser)
        self.assertEqual(superuser.role, UserRole.SUPERADMIN)
        self.assertTrue(superuser.avatar_letter)
        self.assertTrue(superuser.avatar_bg_hex)
