"""P0/P1 smoke-регрессии для стабилизации runtime- и results-потоков."""

import json

from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import User
from apps.content.models import AnalysisPrompt, Game, Scenario, ScenarioPrompt
from apps.dialogs.models import DialogSession, DialogSessionStatus


class DialogP0P1StabilityTests(TestCase):
    """Проверяет критичные P0/P1 сценарии стабильности пользовательского потока.

    Контекст использования:
        Набор покрывает регрессионно-важные кейсы из smoke/security-ветки:
        доступ к чужим результатам, корректная обработка JSON content-type
        с charset и идемпотентность повторного PDF-экспорта.

    Параметры:
        Использует Django test client и тестовую БД.

    Возвращаемое значение:
        Ничего не возвращает; выполняет HTTP/assertions.

    Исключения и особые случаи:
        При нарушении контрактов endpoint-ов тесты падают.

    Побочные эффекты:
        Создаёт тестовых пользователей, контент и диалоги в БД.
    """

    def setUp(self) -> None:
        """Создаёт минимальный опубликованный контент и двух пользователей.

        Контекст использования:
            Подготавливает общие предусловия для P0/P1 runtime-тестов.

        Параметры:
            Параметры отсутствуют.

        Возвращаемое значение:
            Ничего не возвращает.

        Исключения и особые случаи:
            Особые случаи отсутствуют.

        Побочные эффекты:
            Создаёт записи пользователей, игры, сценария и промтов в тестовой БД.
        """

        self.owner = User.objects.create_user(
            email="owner@example.com",
            nickname="Владелец",
            password="StrongPassword123",
            avatar_letter="В",
            avatar_bg_hex="#D6E8FF",
        )
        self.other_user = User.objects.create_user(
            email="other@example.com",
            nickname="Читатель",
            password="StrongPassword123",
            avatar_letter="Ч",
            avatar_bg_hex="#F3D6FF",
        )

        self.game = Game.objects.create(
            slug="p0-game",
            title="P0 игра",
            sort_order=1,
            is_published=True,
            created_by=self.owner,
        )
        self.scenario = Scenario.objects.create(
            game=self.game,
            slug="p0-scenario",
            title="P0 сценарий",
            conditions_text="Условия",
            opening_message_text="Стартовое сообщение",
            sort_order=1,
            is_published=True,
            created_by=self.owner,
        )
        ScenarioPrompt.objects.create(
            scenario=self.scenario,
            title="Игровой",
            prompt_text="Ведите диалог.",
            is_active=True,
            created_by=self.owner,
        )
        AnalysisPrompt.objects.create(
            game=self.game,
            alias="p0-clarity",
            title="Ясность",
            header_text="Ясность ответа",
            comment_text="",
            prompt_text="Оцени ясность.",
            sort_order=1,
            min_rating=0,
            max_rating=5,
            is_active=True,
            created_by=self.owner,
        )

    def _start_owner_dialog(self) -> DialogSession:
        """Запускает диалог владельца и возвращает активную сессию.

        Контекст использования:
            Упрощает подготовку повторяющихся шагов в тестах P0/P1.

        Параметры:
            Параметры отсутствуют.

        Возвращаемое значение:
            Созданный ``DialogSession`` со статусом ``active``.

        Исключения и особые случаи:
            Исключения не ожидаются.

        Побочные эффекты:
            Выполняет HTTP-запрос старта сценария и создаёт диалог в БД.
        """

        self.client.force_login(self.owner)
        self.client.get(reverse("dialogs:start_scenario", kwargs={"scenario_slug": self.scenario.slug}))
        return DialogSession.objects.get(user=self.owner, status=DialogSessionStatus.ACTIVE)

    def test_send_message_accepts_json_content_type_with_charset(self) -> None:
        """P0: send-message принимает JSON content-type с параметром charset.

        Контекст использования:
            Защищает от регрессии, когда валидные JSON-запросы браузера/клиента
            отклоняются из-за суффикса ``; charset=utf-8``.

        Параметры:
            Параметры отсутствуют.

        Возвращаемое значение:
            Ничего не возвращает; проверяет HTTP-статус и payload.

        Исключения и особые случаи:
            При отклонении валидного content-type тест падает.

        Побочные эффекты:
            Создаёт и использует активный диалог владельца.
        """

        dialog = self._start_owner_dialog()

        response = self.client.post(
            reverse("dialogs:send_message", kwargs={"dialog_public_id": dialog.public_id}),
            data=json.dumps({"text": "Тестовое сообщение"}),
            content_type="application/json; charset=utf-8",
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["ok"])

    def test_results_endpoint_is_hidden_for_foreign_user(self) -> None:
        """P0: чужой пользователь не может открыть страницу чужих результатов.

        Контекст использования:
            Покрывает security-требование на запрет доступа к чужим результатам
            по прямому ``dialog_public_id``.

        Параметры:
            Параметры отсутствуют.

        Возвращаемое значение:
            Ничего не возвращает; проверяет 404-ответ.

        Исключения и особые случаи:
            При утечке доступа тест завершается ошибкой.

        Побочные эффекты:
            Создаёт завершённый диалог владельца и выполняет запрос чужим пользователем.
        """

        dialog = self._start_owner_dialog()
        self.client.post(
            reverse("dialogs:send_message", kwargs={"dialog_public_id": dialog.public_id}),
            data=json.dumps({"text": "Сообщение владельца"}),
            content_type="application/json",
        )
        self.client.post(
            reverse("dialogs:finish_dialog", kwargs={"dialog_public_id": dialog.public_id}),
            data=json.dumps({"reason": "manual_feedback"}),
            content_type="application/json",
        )

        self.client.force_login(self.other_user)
        response = self.client.get(reverse("dialogs:dialog_results", kwargs={"dialog_public_id": dialog.public_id}))
        self.assertEqual(response.status_code, 404)

    def test_pdf_export_is_idempotent_for_same_dialog(self) -> None:
        """P1: повторный экспорт PDF для одного результата стабильно успешен.

        Контекст использования:
            Покрывает edge-кейс повторного экспорта без изменения состояния
            диалога и анализа между запросами.

        Параметры:
            Параметры отсутствуют.

        Возвращаемое значение:
            Ничего не возвращает; проверяет ответы двух последовательных экспортов.

        Исключения и особые случаи:
            При нарушении идемпотентности endpoint-а тест падает.

        Побочные эффекты:
            Создаёт завершённый диалог с анализом и вызывает экспорт дважды.
        """

        dialog = self._start_owner_dialog()
        self.client.post(
            reverse("dialogs:send_message", kwargs={"dialog_public_id": dialog.public_id}),
            data=json.dumps({"text": "Подробная обратная связь"}),
            content_type="application/json",
        )
        self.client.post(
            reverse("dialogs:finish_dialog", kwargs={"dialog_public_id": dialog.public_id}),
            data=json.dumps({"reason": "manual_feedback"}),
            content_type="application/json",
        )

        export_url = reverse("dialogs:dialog_export_pdf", kwargs={"dialog_public_id": dialog.public_id})
        first_response = self.client.get(export_url)
        second_response = self.client.get(export_url)

        self.assertEqual(first_response.status_code, 200)
        self.assertEqual(second_response.status_code, 200)
        self.assertEqual(first_response["Content-Type"], "application/pdf")
        self.assertEqual(second_response["Content-Type"], "application/pdf")
        self.assertTrue(first_response.content.startswith(b"%PDF"))
        self.assertTrue(second_response.content.startswith(b"%PDF"))
