"""Smoke-тесты runtime: старт, отправка и завершение диалоговой сессии."""

import json

from django.test import TestCase
from django.urls import reverse

from apps.analysis.models import AnalysisRun
from apps.accounts.models import User
from apps.content.models import AnalysisPrompt, Game, Scenario, ScenarioPrompt
from apps.dialogs.models import DialogEndedReason, DialogMessageRole, DialogSession, DialogSessionStatus


class DialogRuntimeTests(TestCase):
    """Проверяет цикл start/send/finish/abandon и защиту от дублей.

    Контекст использования:
        Гарантирует корректное поведение ключевых runtime endpoint-ов первой версии
        до подключения полноценной аналитики и внешней LLM-интеграции.

    Параметры:
        Использует Django test client и тестовую БД.

    Возвращаемое значение:
        Не возвращает значение; выполняет набор проверок HTTP и состояния БД.

    Исключения и особые случаи:
        Любое нарушение контрактов endpoint-ов приводит к падению теста.

    Побочные эффекты:
        Создаёт тестовые записи игры, сценария, промта и диалога.
    """

    def setUp(self) -> None:
        """Подготавливает пользователя и минимальный контент для запуска чата.

        Контекст использования:
            Формирует baseline-данные для тестов runtime-потока.

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
        AnalysisPrompt.objects.create(
            game=self.game,
            alias="clarity",
            title="Ясность",
            header_text="Конкретика и ясность",
            comment_text="",
            prompt_text="Оцени ясность ответа.",
            sort_order=1,
            min_rating=0,
            max_rating=5,
            is_active=True,
            created_by=self.user,
        )

    def _start_dialog(self) -> DialogSession:
        """Запускает сценарий и возвращает созданный активный диалог.

        Контекст использования:
            Упрощает подготовку предусловий в отдельных тестах runtime-потока.

        Параметры:
            Параметры отсутствуют.

        Возвращаемое значение:
            Объект ``DialogSession`` со статусом ``active``.

        Исключения и особые случаи:
            Исключения не ожидаются.

        Побочные эффекты:
            Выполняет HTTP-запрос старта и создаёт диалог в БД.
        """

        self.client.get(reverse("dialogs:start_scenario", kwargs={"scenario_slug": self.scenario.slug}))
        return DialogSession.objects.get(user=self.user, status=DialogSessionStatus.ACTIVE)

    def test_start_scenario_creates_dialog_and_opening_message(self) -> None:
        """Проверяет создание активного диалога и первого assistant-сообщения."""

        self.client.force_login(self.user)
        response = self.client.get(reverse("dialogs:start_scenario", kwargs={"scenario_slug": self.scenario.slug}))

        dialog = DialogSession.objects.get(user=self.user, status=DialogSessionStatus.ACTIVE)
        self.assertRedirects(response, reverse("dialogs:dialog_detail", kwargs={"dialog_public_id": dialog.public_id}))
        first_message = dialog.messages.get(sequence_no=1)
        self.assertEqual(first_message.role, DialogMessageRole.ASSISTANT)

    def test_send_message_returns_json_with_user_and_assistant_messages(self) -> None:
        """Проверяет JSON-контракт endpoint-а send-message."""

        self.client.force_login(self.user)
        dialog = self._start_dialog()

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

    def test_finish_manual_sets_finished_or_analysis_skipped(self) -> None:
        """Проверяет ручное завершение с правильным конечным статусом диалога."""

        self.client.force_login(self.user)
        dialog = self._start_dialog()

        response = self.client.post(
            reverse("dialogs:finish_dialog", kwargs={"dialog_public_id": dialog.public_id}),
            data=json.dumps({"reason": "manual_feedback"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)

        dialog.refresh_from_db()
        self.assertEqual(dialog.status, DialogSessionStatus.ANALYSIS_SKIPPED)
        self.assertEqual(dialog.ended_reason, DialogEndedReason.NO_USER_MESSAGES)

    def test_finish_timeout_after_user_message(self) -> None:
        """Проверяет таймерное завершение после пользовательской реплики."""

        self.client.force_login(self.user)
        dialog = self._start_dialog()
        self.client.post(
            reverse("dialogs:send_message", kwargs={"dialog_public_id": dialog.public_id}),
            data=json.dumps({"text": "Продолжим разговор."}),
            content_type="application/json",
        )

        response = self.client.post(
            reverse("dialogs:finish_dialog", kwargs={"dialog_public_id": dialog.public_id}),
            data=json.dumps({"reason": "timeout"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        dialog.refresh_from_db()
        self.assertEqual(dialog.status, DialogSessionStatus.FINISHED)
        self.assertEqual(dialog.ended_reason, DialogEndedReason.TIMEOUT)

    def test_abandon_marks_dialog_as_aborted(self) -> None:
        """Проверяет обработку события ухода со страницы через abandon endpoint."""

        self.client.force_login(self.user)
        dialog = self._start_dialog()

        response = self.client.post(
            reverse("dialogs:abandon_dialog", kwargs={"dialog_public_id": dialog.public_id}),
            data={"reason": "page_leave"},
        )

        self.assertEqual(response.status_code, 200)
        dialog.refresh_from_db()
        self.assertEqual(dialog.status, DialogSessionStatus.ABORTED)
        self.assertEqual(dialog.ended_reason, DialogEndedReason.PAGE_LEAVE)

    def test_duplicate_finish_returns_dialog_not_active(self) -> None:
        """Проверяет защиту от повторного завершения уже закрытого диалога."""

        self.client.force_login(self.user)
        dialog = self._start_dialog()

        self.client.post(
            reverse("dialogs:finish_dialog", kwargs={"dialog_public_id": dialog.public_id}),
            data=json.dumps({"reason": "manual_feedback"}),
            content_type="application/json",
        )
        second_response = self.client.post(
            reverse("dialogs:finish_dialog", kwargs={"dialog_public_id": dialog.public_id}),
            data=json.dumps({"reason": "manual_feedback"}),
            content_type="application/json",
        )

        self.assertEqual(second_response.status_code, 409)
        self.assertEqual(second_response.json()["code"], "dialog_not_active")

    def test_results_page_contains_export_button_and_transcript(self) -> None:
        """Проверяет ключевые элементы экрана результатов после завершения диалога.

        Контекст использования:
            Гарантирует, что страница результата содержит экспорт в PDF,
            сумму баллов и блок транскрипта в соответствии со спецификацией.

        Параметры:
            Параметры отсутствуют.

        Возвращаемое значение:
            Ничего не возвращает; выполняет HTTP и content-assertions.

        Исключения и особые случаи:
            При несоответствии шаблона требованиям тест падает.

        Побочные эффекты:
            Создаёт и завершает тестовый диалог с запуском анализа.
        """

        self.client.force_login(self.user)
        dialog = self._start_dialog()
        self.client.post(
            reverse("dialogs:send_message", kwargs={"dialog_public_id": dialog.public_id}),
            data=json.dumps({"text": "Даю развёрнутую обратную связь по задаче."}),
            content_type="application/json",
        )
        self.client.post(
            reverse("dialogs:finish_dialog", kwargs={"dialog_public_id": dialog.public_id}),
            data=json.dumps({"reason": "manual_feedback"}),
            content_type="application/json",
        )

        response = self.client.get(reverse("dialogs:dialog_results", kwargs={"dialog_public_id": dialog.public_id}))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Экспорт результатов в PDF")
        self.assertContains(response, "Транскрипт диалога")
        self.assertContains(response, "Сумма:")

    def test_export_pdf_returns_attachment_for_owner(self) -> None:
        """Проверяет успешную выдачу PDF-файла владельцу диалога.

        Контекст использования:
            Покрывает позитивный поток TC-PDF-001/TC-PDF-004 на уровне endpoint-а.

        Параметры:
            Параметры отсутствуют.

        Возвращаемое значение:
            Ничего не возвращает; выполняет проверки HTTP-заголовков и сигнатуры PDF.

        Исключения и особые случаи:
            При невалидном ответе endpoint-а тест падает.

        Побочные эффекты:
            Создаёт завершённый диалог с анализом в тестовой БД.
        """

        self.client.force_login(self.user)
        dialog = self._start_dialog()
        self.client.post(
            reverse("dialogs:send_message", kwargs={"dialog_public_id": dialog.public_id}),
            data=json.dumps({"text": "Поясняю решение по этапам и рискам."}),
            content_type="application/json",
        )
        self.client.post(
            reverse("dialogs:finish_dialog", kwargs={"dialog_public_id": dialog.public_id}),
            data=json.dumps({"reason": "manual_feedback"}),
            content_type="application/json",
        )

        response = self.client.get(reverse("dialogs:dialog_export_pdf", kwargs={"dialog_public_id": dialog.public_id}))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertIn("attachment;", response["Content-Disposition"])
        self.assertTrue(response.content.startswith(b"%PDF"))
        self.assertTrue(AnalysisRun.objects.filter(dialog=dialog).exists())

    def test_export_pdf_is_forbidden_for_foreign_user(self) -> None:
        """Проверяет, что пользователь не может скачать чужой PDF по прямой ссылке.

        Контекст использования:
            Покрывает security-требование TC-PDF-004 для endpoint-а экспорта.

        Параметры:
            Параметры отсутствуют.

        Возвращаемое значение:
            Ничего не возвращает; проверяет 404 для чужого диалога.

        Исключения и особые случаи:
            При утечке доступа тест падает.

        Побочные эффекты:
            Создаёт второго пользователя и его диалог.
        """

        foreign_user = User.objects.create_user(
            email="foreign@example.com",
            nickname="Чужой",
            password="StrongPassword123",
            avatar_letter="Ч",
            avatar_bg_hex="#D0F7E5",
        )

        self.client.force_login(foreign_user)
        foreign_dialog = self._start_dialog()
        self.client.post(
            reverse("dialogs:send_message", kwargs={"dialog_public_id": foreign_dialog.public_id}),
            data=json.dumps({"text": "Сообщение владельца диалога."}),
            content_type="application/json",
        )
        self.client.post(
            reverse("dialogs:finish_dialog", kwargs={"dialog_public_id": foreign_dialog.public_id}),
            data=json.dumps({"reason": "manual_feedback"}),
            content_type="application/json",
        )

        self.client.force_login(self.user)
        response = self.client.get(reverse("dialogs:dialog_export_pdf", kwargs={"dialog_public_id": foreign_dialog.public_id}))
        self.assertEqual(response.status_code, 404)
