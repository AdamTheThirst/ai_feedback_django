"""Тесты прав доступа и владения объектами в контурной админ-панели."""

from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import User, UserRole
from apps.content.models import Game


class BackofficeContentPermissionsTests(TestCase):
    """Проверяет доступ к CRUD контентных сущностей по ролям и владению.

    Контекст использования:
        Гарантирует соблюдение ключевого правила: обычный администратор работает
        только со своими объектами, а супер-администратор имеет глобальный доступ.

    Параметры:
        Использует тестовый клиент Django и тестовую БД.

    Возвращаемое значение:
        Не возвращает значение; выполняет набор проверок ответов HTTP.

    Исключения и особые случаи:
        Любое нарушение ожидаемой матрицы прав приводит к падению теста.

    Побочные эффекты:
        Создаёт тестовые учётки и объекты игры в тестовой БД.
    """

    def setUp(self) -> None:
        """Подготавливает пользователей разных ролей и тестовые игры.

        Контекст использования:
            Используется как единый setup для сценариев проверки прав.

        Параметры:
            Параметры отсутствуют.

        Возвращаемое значение:
            Ничего не возвращает.

        Исключения и особые случаи:
            Исключения не ожидаются.

        Побочные эффекты:
            Создаёт записи пользователей и игр в тестовой БД.
        """

        self.regular_user = User.objects.create_user(
            email="user@example.com",
            nickname="Пользователь",
            password="StrongPassword123",
            role=UserRole.USER,
            avatar_letter="П",
            avatar_bg_hex="#F7D6D0",
        )
        self.admin_1 = User.objects.create_user(
            email="admin1@example.com",
            nickname="Админ1",
            password="StrongPassword123",
            role=UserRole.ADMIN,
            is_staff=True,
            avatar_letter="А",
            avatar_bg_hex="#FDE2C8",
        )
        self.admin_2 = User.objects.create_user(
            email="admin2@example.com",
            nickname="Админ2",
            password="StrongPassword123",
            role=UserRole.ADMIN,
            is_staff=True,
            avatar_letter="А",
            avatar_bg_hex="#F8EFB7",
        )
        self.superadmin = User.objects.create_user(
            email="super@example.com",
            nickname="Супер",
            password="StrongPassword123",
            role=UserRole.SUPERADMIN,
            is_staff=True,
            avatar_letter="С",
            avatar_bg_hex="#D9F2C4",
        )

        self.game_admin_1 = Game.objects.create(
            slug="game-admin-1",
            title="Игра админа 1",
            sort_order=1,
            is_published=True,
            created_by=self.admin_1,
        )
        self.game_admin_2 = Game.objects.create(
            slug="game-admin-2",
            title="Игра админа 2",
            sort_order=2,
            is_published=True,
            created_by=self.admin_2,
        )

    def test_regular_user_cannot_access_backoffice(self) -> None:
        """Проверяет запрет доступа обычному пользователю в контур бэкофиса.

        Контекст использования:
            Валидирует базовую ролевую изоляцию административных маршрутов.

        Параметры:
            Параметры отсутствуют.

        Возвращаемое значение:
            Ничего не возвращает.

        Исключения и особые случаи:
            Исключения не ожидаются.

        Побочные эффекты:
            Побочные эффекты отсутствуют.
        """

        self.client.force_login(self.regular_user)
        response = self.client.get(reverse("adminpanel:dashboard"))
        self.assertEqual(response.status_code, 403)

    def test_admin_sees_only_owned_games(self) -> None:
        """Проверяет, что администратор видит только собственные игры.

        Контекст использования:
            Покрывает ключевое правило владения объектами для роли admin.

        Параметры:
            Параметры отсутствуют.

        Возвращаемое значение:
            Ничего не возвращает.

        Исключения и особые случаи:
            Исключения не ожидаются.

        Побочные эффекты:
            Побочные эффекты отсутствуют.
        """

        self.client.force_login(self.admin_1)
        response = self.client.get(reverse("adminpanel:game_list"))
        self.assertContains(response, "Игра админа 1")
        self.assertNotContains(response, "Игра админа 2")

    def test_admin_cannot_edit_foreign_game(self) -> None:
        """Проверяет блокировку редактирования чужой игры обычным админом.

        Контекст использования:
            Серверная проверка прав должна сработать независимо от интерфейса.

        Параметры:
            Параметры отсутствуют.

        Возвращаемое значение:
            Ничего не возвращает.

        Исключения и особые случаи:
            Исключения не ожидаются.

        Побочные эффекты:
            Побочные эффекты отсутствуют.
        """

        self.client.force_login(self.admin_1)
        response = self.client.get(
            reverse("adminpanel:game_update", kwargs={"pk": self.game_admin_2.pk})
        )
        self.assertEqual(response.status_code, 403)

    def test_superadmin_can_edit_any_game(self) -> None:
        """Проверяет глобальный доступ супер-админа к контентным объектам.

        Контекст использования:
            Подтверждает админские контуры для роли супер-администратора.

        Параметры:
            Параметры отсутствуют.

        Возвращаемое значение:
            Ничего не возвращает.

        Исключения и особые случаи:
            Исключения не ожидаются.

        Побочные эффекты:
            Побочные эффекты отсутствуют.
        """

        self.client.force_login(self.superadmin)
        response = self.client.get(
            reverse("adminpanel:game_update", kwargs={"pk": self.game_admin_2.pk})
        )
        self.assertEqual(response.status_code, 200)

    def test_superadmin_can_access_user_management(self) -> None:
        """Проверяет доступ супер-админа к разделу пользователей в бэкофисе.

        Контекст использования:
            Подтверждает требование управления пользователями только для
            роли супер-администратора.

        Параметры:
            Параметры отсутствуют.

        Возвращаемое значение:
            Ничего не возвращает; проверяет успешный HTTP-ответ.

        Исключения и особые случаи:
            Исключения не ожидаются.

        Побочные эффекты:
            Побочные эффекты отсутствуют.
        """

        self.client.force_login(self.superadmin)
        response = self.client.get(reverse("adminpanel:user_list"))
        self.assertEqual(response.status_code, 200)

    def test_admin_cannot_access_user_management(self) -> None:
        """Проверяет запрет доступа обычному администратору к списку пользователей.

        Контекст использования:
            Закрывает security-ограничение раздела управления пользователями.

        Параметры:
            Параметры отсутствуют.

        Возвращаемое значение:
            Ничего не возвращает; проверяет ответ ``403``.

        Исключения и особые случаи:
            Исключения не ожидаются.

        Побочные эффекты:
            Побочные эффекты отсутствуют.
        """

        self.client.force_login(self.admin_1)
        response = self.client.get(reverse("adminpanel:user_list"))
        self.assertEqual(response.status_code, 403)

    def test_superadmin_can_create_and_toggle_user(self) -> None:
        """Проверяет создание и исключение пользователя супер-администратором.

        Контекст использования:
            Закрывает бизнес-требование управления пользовательскими записями
            из внутренней административной панели.

        Параметры:
            Параметры отсутствуют.

        Возвращаемое значение:
            Ничего не возвращает; проверяет изменение состояния БД.

        Исключения и особые случаи:
            Исключения не ожидаются.

        Побочные эффекты:
            Создаёт пользователя и меняет его ``is_active``.
        """

        self.client.force_login(self.superadmin)
        create_response = self.client.post(
            reverse("adminpanel:user_create"),
            data={
                "email": "new.by.super@example.com",
                "nickname": "Новый",
                "role": UserRole.USER,
                "is_active": "on",
                "password1": "StrongPassword123",
                "password2": "StrongPassword123",
            },
        )
        self.assertEqual(create_response.status_code, 302)
        created_user = User.objects.get(email="new.by.super@example.com")
        self.assertTrue(created_user.is_active)

        toggle_response = self.client.post(
            reverse("adminpanel:user_toggle_active", kwargs={"pk": created_user.pk})
        )
        self.assertEqual(toggle_response.status_code, 302)
        created_user.refresh_from_db()
        self.assertFalse(created_user.is_active)
