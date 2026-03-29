"""Smoke-тесты runtime: старт, отправка и завершение диалоговой сессии."""

import json
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse

from apps.analysis.models import AnalysisRun
from apps.accounts.models import User
from apps.accounts.models import UserRole
from apps.auditlog.models import AuditLogEntry
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

    def test_dialog_detail_renders_new_chat_layout_blocks(self) -> None:
        """Проверяет базовую структуру нового UI игрового чат-экрана.

        Контекст использования:
            Фиксирует ключевые контейнеры mobile-first композиции: шапка,
            кнопка завершения, лента сообщений и нижняя зона ввода.

        Параметры:
            Параметры отсутствуют.

        Возвращаемое значение:
            Ничего не возвращает; проверяет HTML-ответ страницы диалога.

        Исключения и особые случаи:
            При отсутствии ожидаемых блоков тест считается проваленным.

        Побочные эффекты:
            Создаёт активный диалог для рендера шаблона.
        """

        self.client.force_login(self.user)
        dialog = self._start_dialog()

        response = self.client.get(reverse("dialogs:dialog_detail", kwargs={"dialog_public_id": dialog.public_id}))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "class=\"chat-card\"")
        self.assertContains(response, "id=\"finish-button\"")
        self.assertContains(response, "class=\"chat-conditions\"")
        self.assertContains(response, "id=\"chat-messages\"")
        self.assertContains(response, "class=\"chat-composer\"")
        self.assertContains(response, "/media/ui/logo_mini.png")

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

    @patch("apps.dialogs.services.runtime.call_chat_completion")
    @patch("apps.dialogs.services.runtime.get_active_platform_settings")
    def test_send_message_uses_llm_response_text(self, settings_mock, llm_mock) -> None:
        """Проверяет, что runtime использует ответ LLM в реплике персонажа.

        Контекст использования:
            Подтверждает, что заглушка удалена и сообщение ассистента берётся
            из внешнего LLM-вызова (замоканного в тесте).

        Параметры:
            settings_mock: Мок платформенных настроек.
            llm_mock: Мок OpenAI-compatible вызова.

        Возвращаемое значение:
            Ничего не возвращает; проверяет JSON ответа endpoint-а.

        Исключения и особые случаи:
            Исключения не ожидаются при корректных моках.

        Побочные эффекты:
            Создаёт и использует активный диалог в тестовой БД.
        """

        settings_mock.return_value = None
        llm_mock.return_value = "Ответ персонажа из LLM"
        self.client.force_login(self.user)
        dialog = self._start_dialog()

        response = self.client.post(
            reverse("dialogs:send_message", kwargs={"dialog_public_id": dialog.public_id}),
            data=json.dumps({"text": "Привет"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["data"]["assistant_message"]["text"], "Ответ персонажа из LLM")

    @patch("apps.dialogs.services.runtime.call_chat_completion")
    @patch("apps.dialogs.services.runtime.get_active_platform_settings")
    def test_send_message_returns_diagnostic_error_for_admin_chat(self, settings_mock, llm_mock) -> None:
        """Проверяет диагностическое сообщение об ошибке AI для администратора.

        Контекст использования:
            Нужен для локальной отладки интеграции с LLM: администратор должен
            увидеть в чате не только fallback, но и описание причины сбоя.

        Параметры:
            settings_mock: Мок активных PlatformSettings.
            llm_mock: Мок вызова внешнего LLM-клиента.

        Возвращаемое значение:
            Ничего не возвращает; выполняет проверки JSON-ответа runtime endpoint-а.

        Исключения и особые случаи:
            Если endpoint не вернул диагностический текст, тест падает.

        Побочные эффекты:
            Создаёт отдельного admin-пользователя и запускает диалог в тестовой БД.
        """

        settings_mock.return_value = None
        llm_mock.side_effect = RuntimeError("Connection refused")

        admin_user = User.objects.create_user(
            email="admin.chat@example.com",
            nickname="Админ-чат",
            password="StrongPassword123",
            role=UserRole.ADMIN,
            is_staff=True,
            avatar_letter="А",
            avatar_bg_hex="#D6E8FF",
        )
        self.client.force_login(admin_user)
        self.client.get(reverse("dialogs:start_scenario", kwargs={"scenario_slug": self.scenario.slug}))
        admin_dialog = DialogSession.objects.get(user=admin_user, status=DialogSessionStatus.ACTIVE)

        response = self.client.post(
            reverse("dialogs:send_message", kwargs={"dialog_public_id": admin_dialog.public_id}),
            data=json.dumps({"text": "Проверка подключения"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        assistant_text = response.json()["data"]["assistant_message"]["text"]
        self.assertIn("Ошибка подключения к AI", assistant_text)
        self.assertIn("RuntimeError", assistant_text)
        self.assertIn("Connection refused", assistant_text)

    def test_send_message_rejects_non_json_content_type(self) -> None:
        """Проверяет отклонение send-message без application/json.

        Контекст использования:
            Покрывает hardening-контракт endpoint-а, чтобы сервер не принимал
            произвольный content-type для JSON-операции отправки сообщения.

        Параметры:
            Параметры отсутствуют.

        Возвращаемое значение:
            Ничего не возвращает; выполняет проверки статуса и кода ошибки.

        Исключения и особые случаи:
            При нарушении контракта endpoint-а тест падает.

        Побочные эффекты:
            Создаёт активный диалог для отправки запроса.
        """

        self.client.force_login(self.user)
        dialog = self._start_dialog()

        response = self.client.post(
            reverse("dialogs:send_message", kwargs={"dialog_public_id": dialog.public_id}),
            data={"text": "Не JSON payload"},
        )

        self.assertEqual(response.status_code, 415)
        self.assertEqual(response.json()["code"], "unsupported_content_type")
        self.assertTrue(AuditLogEntry.objects.filter(event_type="dialogs.send.invalid_content_type").exists())

    def test_send_message_rate_limit_returns_429(self) -> None:
        """Проверяет, что rate-limit блокирует слишком частые отправки.

        Контекст использования:
            Закрывает security-сценарий защиты от burst-спама на send endpoint.

        Параметры:
            Параметры отсутствуют.

        Возвращаемое значение:
            Ничего не возвращает; проверяет код ошибки и HTTP-статус.

        Исключения и особые случаи:
            Лимит временно занижается через patch только внутри теста.

        Побочные эффекты:
            Создаёт активный диалог и выполняет серию POST-запросов.
        """

        self.client.force_login(self.user)
        dialog = self._start_dialog()
        endpoint = reverse("dialogs:send_message", kwargs={"dialog_public_id": dialog.public_id})

        with patch("apps.dialogs.views.consume_send_message_rate_limit", side_effect=[True, False]):
            first_response = self.client.post(
                endpoint,
                data=json.dumps({"text": "Первое сообщение"}),
                content_type="application/json",
            )
            second_response = self.client.post(
                endpoint,
                data=json.dumps({"text": "Второе сообщение"}),
                content_type="application/json",
            )

        self.assertEqual(first_response.status_code, 200)
        self.assertEqual(second_response.status_code, 429)
        self.assertEqual(second_response.json()["code"], "rate_limited")
        self.assertTrue(AuditLogEntry.objects.filter(event_type="dialogs.send.rate_limited").exists())

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
