"""Smoke-тесты runtime: старт сценария, чат и отправка сообщений."""

import json

from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import User
from apps.content.models import Game, Scenario, ScenarioPrompt
from apps.dialogs.models import DialogMessageRole, DialogSession, DialogSessionStatus


class DialogRuntimeTests(TestCase):
    """Проверяет базовый runtime-цикл start/send/pending для чата.

    Контекст использования:
        Гарантирует, что пользователь может запустить сценарий, получить страницу
        диалога и отправить сообщение с сохранением ответа ассистента.

    Параметры:
        Использует Django test client и тестовую БД.

    Возвращаемое значение:
        Не возвращает значение; выполняет набор проверок HTTP и БД.

    Исключения и особые случаи:
        Любое нарушение контракта старт/отправка приводит к падению теста.

    Побочные эффекты:
        Создаёт тестовые записи игры, сценария, промта и диалога в БД.
    """

    def setUp(self) -> None:
        """Подготавливает пользователя и минимальный контент для запуска чата.

        Контекст использования:
            Формирует baseline-данные для всех тестовых сценариев runtime.

        Параметры:
            Параметры отсутствуют.

        Возвращаемое значение:
            Ничего не возвращает.

        Исключения и особые случаи:
            Исключения не ожидаются.

        Побочные эффекты:
            Создаёт записи в тестовой БД.
        """

        self.user = User.objects.create_user(
            email="dialog.user@example.com",
            nickname="Диалог",
            password="StrongPassword123",
            avatar_letter="Д",
            avatar_bg_hex="#F7D6D0",
        )
        self.game = Game.objects.create(
            slug="feedback-game",
            title="Тренажёр",
            sort_order=1,
            is_published=True,
            created_by=self.user,
        )
        self.scenario = Scenario.objects.create(
            game=self.game,
            slug="manager-talk",
            title="Разговор с менеджером",
            conditions_text="Вы говорите с менеджером о сроках.",
            opening_message_text="Здравствуйте! Давайте обсудим ситуацию.",
            sort_order=1,
            is_published=True,
            created_by=self.user,
        )
        ScenarioPrompt.objects.create(
            scenario=self.scenario,
            title="Основной промт",
            prompt_text="Ведите ролевой диалог.",
            is_active=True,
            created_by=self.user,
        )

    def test_start_scenario_creates_dialog_and_opening_message(self) -> None:
        """Проверяет создание активного диалога и стартового assistant-сообщения.

        Контекст использования:
            Покрывает начальную часть runtime-цикла перед отправкой сообщений.

        Параметры:
            Параметры отсутствуют.

        Возвращаемое значение:
            Ничего не возвращает.

        Исключения и особые случаи:
            Исключения не ожидаются.

        Побочные эффекты:
            Создаёт ``DialogSession`` и первое сообщение в БД.
        """

        self.client.force_login(self.user)
        response = self.client.get(
            reverse("dialogs:start_scenario", kwargs={"scenario_slug": self.scenario.slug})
        )

        dialog = DialogSession.objects.get(user=self.user, status=DialogSessionStatus.ACTIVE)
        self.assertRedirects(
            response,
            reverse("dialogs:dialog_detail", kwargs={"dialog_public_id": dialog.public_id}),
        )
        first_message = dialog.messages.get(sequence_no=1)
        self.assertEqual(first_message.role, DialogMessageRole.ASSISTANT)

    def test_send_message_returns_json_with_user_and_assistant_messages(self) -> None:
        """Проверяет JSON-контракт endpoint-а send-message.

        Контекст использования:
            Подтверждает базовый async-цикл чата без полной перезагрузки страницы.

        Параметры:
            Параметры отсутствуют.

        Возвращаемое значение:
            Ничего не возвращает.

        Исключения и особые случаи:
            Исключения не ожидаются.

        Побочные эффекты:
            Создаёт две новые записи ``DialogMessage`` и обновляет счётчики.
        """

        self.client.force_login(self.user)
        self.client.get(reverse("dialogs:start_scenario", kwargs={"scenario_slug": self.scenario.slug}))
        dialog = DialogSession.objects.get(user=self.user, status=DialogSessionStatus.ACTIVE)

        response = self.client.post(
            reverse("dialogs:send_message", kwargs={"dialog_public_id": dialog.public_id}),
            data=json.dumps({"text": "Мне нужен перенос срока."}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["data"]["user_message"]["role"], "user")
        self.assertEqual(payload["data"]["assistant_message"]["role"], "assistant")
