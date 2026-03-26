"""Тесты сервиса генерации PDF по результатам диалога."""

from django.test import TestCase

from apps.accounts.models import User
from apps.analysis.services.runner import run_analysis_for_dialog
from apps.content.models import AnalysisPrompt, Game, Scenario, ScenarioPrompt
from apps.dialogs.models import DialogMessage, DialogMessageRole
from apps.dialogs.services.runtime import create_dialog_session, finish_dialog
from apps.exports.services.pdf import build_dialog_results_pdf
from apps.dialogs.services.results import build_dialog_results_view_model


class PdfExportServiceTests(TestCase):
    """Проверяет базовую корректность формирования PDF-документа.

    Контекст использования:
        Даёт smoke-покрытие сервиса ``build_dialog_results_pdf`` и защищает
        от регрессий, когда экспорт перестаёт выдавать валидный бинарный поток.

    Параметры:
        Использует тестовую БД Django и локальные ORM-данные.

    Возвращаемое значение:
        Не возвращает значения; выполняет проверки бинарного содержимого.

    Исключения и особые случаи:
        Любая ошибка сборки PDF приводит к падению теста.

    Побочные эффекты:
        Создаёт тестовые сущности игры, сценария, диалога и анализа.
    """

    def test_build_pdf_returns_pdf_signature(self) -> None:
        """Проверяет, что сервис возвращает поток с сигнатурой PDF.

        Контекст использования:
            Подтверждает работоспособность формирования документа на данных
            завершённого диалога с хотя бы одним аналитическим критерием.

        Параметры:
            Параметры отсутствуют.

        Возвращаемое значение:
            Ничего не возвращает; выполняет assertions над байтами ответа.

        Исключения и особые случаи:
            При ошибке генерации или пустом выходе тест завершается ошибкой.

        Побочные эффекты:
            Создаёт и завершает тестовый диалог, запускает анализ.
        """

        user = User.objects.create_user(
            email="pdf.user@example.com",
            nickname="PDF",
            password="StrongPassword123",
            avatar_letter="P",
            avatar_bg_hex="#FFE7C2",
        )
        game = Game.objects.create(
            slug="pdf-game",
            title="PDF игра",
            sort_order=1,
            is_published=True,
            created_by=user,
        )
        scenario = Scenario.objects.create(
            game=game,
            slug="pdf-scenario",
            title="PDF сценарий",
            conditions_text="Условия",
            opening_message_text="Старт",
            sort_order=1,
            is_published=True,
            created_by=user,
        )
        scenario_prompt = ScenarioPrompt.objects.create(
            scenario=scenario,
            title="Игровой промт",
            prompt_text="Веди диалог.",
            is_active=True,
            created_by=user,
        )
        AnalysisPrompt.objects.create(
            game=game,
            alias="quality",
            title="Качество",
            header_text="Качество обратной связи",
            comment_text="",
            prompt_text="Оцени качество.",
            sort_order=1,
            min_rating=0,
            max_rating=5,
            is_active=True,
            created_by=user,
        )

        dialog = create_dialog_session(user_id=user.id, scenario=scenario, scenario_prompt=scenario_prompt)
        DialogMessage.objects.create(
            dialog=dialog,
            sequence_no=2,
            role=DialogMessageRole.USER,
            text="Подготовил обратную связь с фактами и примерами.",
            char_count=47,
            llm_request_id="",
        )
        dialog.user_message_count = 1
        dialog.assistant_message_count = 1
        dialog.save(update_fields=["user_message_count", "assistant_message_count", "updated_at"])

        finished_dialog = finish_dialog(dialog=dialog, reason="manual_feedback")
        run_analysis_for_dialog(finished_dialog)
        view_model = build_dialog_results_view_model(finished_dialog)
        pdf_bytes = build_dialog_results_pdf(view_model)

        self.assertTrue(pdf_bytes.startswith(b"%PDF"))
        self.assertGreater(len(pdf_bytes), 300)
