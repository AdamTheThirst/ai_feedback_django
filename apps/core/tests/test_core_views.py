"""Smoke-тесты корневого входа, главной страницы и заглушек."""

from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import User


class CoreViewsTests(TestCase):
    """Проверяет базовую навигацию пользователя после авторизации.

    Контекст использования:
        Подтверждает доступность главной страницы и заглушек личного кабинета
        и энциклопедии без внедрения полного функционала этих разделов.

    Параметры:
        Использует тестовый HTTP-клиент Django.

    Возвращаемое значение:
        Не возвращает значение; выполняет проверки response-кодов и редиректов.

    Исключения и особые случаи:
        Любое несоответствие ожидаемому маршруту приводит к падению теста.

    Побочные эффекты:
        Создаёт тестового пользователя в тестовой базе данных.
    """

    def setUp(self) -> None:
        """Создаёт тестового пользователя для сценариев авторизованного доступа.

        Контекст использования:
            Подготавливает единые входные данные для всех тестов класса.

        Параметры:
            Параметры отсутствуют.

        Возвращаемое значение:
            Ничего не возвращает.

        Исключения и особые случаи:
            Исключения не ожидаются.

        Побочные эффекты:
            Добавляет запись пользователя в тестовую БД.
        """

        self.user = User.objects.create_user(
            email="core.user@example.com",
            nickname="Главный",
            password="StrongPassword123",
            avatar_letter="Г",
            avatar_bg_hex="#F7D6D0",
        )

    def test_root_redirects_guest_to_login(self) -> None:
        """Проверяет редирект гостя с ``/`` на страницу входа.

        Контекст использования:
            Покрывает публичный корневой вход до авторизации.

        Параметры:
            Параметры отсутствуют.

        Возвращаемое значение:
            Ничего не возвращает.

        Исключения и особые случаи:
            Исключения не ожидаются.

        Побочные эффекты:
            Побочные эффекты отсутствуют.
        """

        response = self.client.get(reverse("core:root"))
        self.assertRedirects(response, reverse("accounts:login"))

    def test_root_redirects_authenticated_to_home(self) -> None:
        """Проверяет редирект авторизованного пользователя с ``/`` на ``/home/``.

        Контекст использования:
            Подтверждает корректную точку входа после успешной аутентификации.

        Параметры:
            Параметры отсутствуют.

        Возвращаемое значение:
            Ничего не возвращает.

        Исключения и особые случаи:
            Исключения не ожидаются.

        Побочные эффекты:
            Открывает сессию пользователя в тестовом клиенте.
        """

        self.client.force_login(self.user)
        response = self.client.get(reverse("core:root"))
        self.assertRedirects(response, reverse("content:game_list"))

    def test_placeholders_are_available_for_authenticated_user(self) -> None:
        """Проверяет доступность заглушек профиля и энциклопедии после входа.

        Контекст использования:
            Подтверждает наличие обязательных точек входа V1 в будущие разделы.

        Параметры:
            Параметры отсутствуют.

        Возвращаемое значение:
            Ничего не возвращает.

        Исключения и особые случаи:
            Исключения не ожидаются.

        Побочные эффекты:
            Побочные эффекты отсутствуют.
        """

        self.client.force_login(self.user)

        profile_response = self.client.get(reverse("core:profile_placeholder"))
        kb_response = self.client.get(reverse("core:knowledge_base_placeholder"))

        self.assertEqual(profile_response.status_code, 200)
        self.assertEqual(kb_response.status_code, 200)
