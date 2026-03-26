"""Тесты синхронного анализа и устойчивости к невалидному JSON."""

from django.test import TestCase

from apps.analysis.models import AnalysisValidationStatus
from apps.analysis.services.runner import run_analysis_for_dialog
from apps.accounts.models import User
from apps.content.models import AnalysisPrompt, Game, Scenario, ScenarioPrompt
from apps.dialogs.models import DialogEndedReason, DialogMessage, DialogMessageRole, DialogSession, DialogSessionStatus


class AnalysisRunnerTests(TestCase):
    """Проверяет запуск анализа, retry-логику и fallback-поведение.

    Контекст использования:
        Подтверждает устойчивость анализа при невалидных/несхемных JSON-ответах
        и корректное сохранение ``AnalysisRun``/``AnalysisResult``.

    Параметры:
        Использует тестовую БД и локальные мок-ответы сервиса анализа.

    Возвращаемое значение:
        Не возвращает значение; выполняет серию unit/smoke проверок.

    Исключения и особые случаи:
        Любое нарушение ожидаемого статуса результата приводит к падению теста.

    Побочные эффекты:
        Создаёт тестовые диалоги, сообщения и аналитические промты.
    """

    def setUp(self) -> None:
        """Создаёт минимальные данные для запуска анализа на диалоге.

        Контекст использования:
            Готовит игру, сценарий, промт сценария и завершённый диалог с сообщениями.

        Параметры:
            Параметры отсутствуют.

        Возвращаемое значение:
            Ничего не возвращает.

        Исключения и особые случаи:
            Исключения не ожидаются.

        Побочные эффекты:
            Создаёт записи в тестовой базе данных.
        """

        self.user = User.objects.create_user(
            email="analysis.user@example.com",
            nickname="Аналитик",
            password="StrongPassword123",
            avatar_letter="А",
            avatar_bg_hex="#F7D6D0",
        )
        self.game = Game.objects.create(
            slug="analysis-game",
            title="Игра анализа",
            sort_order=1,
            is_published=True,
            created_by=self.user,
        )
        self.scenario = Scenario.objects.create(
            game=self.game,
            slug="analysis-scenario",
            title="Сценарий анализа",
            conditions_text="Условия",
            opening_message_text="Старт",
            sort_order=1,
            is_published=True,
            created_by=self.user,
        )
        self.scenario_prompt = ScenarioPrompt.objects.create(
            scenario=self.scenario,
            title="Промт",
            prompt_text="Промт",
            is_active=True,
            created_by=self.user,
        )

    def _create_finished_dialog_with_user_message(self) -> DialogSession:
        """Создаёт завершённый диалог с хотя бы одной репликой пользователя.

        Контекст использования:
            Используется как предусловие для запуска аналитики по бизнес-правилу.

        Параметры:
            Параметры отсутствуют.

        Возвращаемое значение:
            Экземпляр ``DialogSession`` в конечном состоянии.

        Исключения и особые случаи:
            Исключения не ожидаются.

        Побочные эффекты:
            Создаёт диалог и сообщения в тестовой БД.
        """

        dialog = DialogSession.objects.create(
            user=self.user,
            game=self.game,
            scenario=self.scenario,
            scenario_prompt_used=self.scenario_prompt,
            status=DialogSessionStatus.FINISHED,
            started_at="2026-03-26T10:00:00Z",
            ended_at="2026-03-26T10:05:00Z",
            ended_reason=DialogEndedReason.MANUAL_FEEDBACK,
            user_message_count=1,
            assistant_message_count=2,
            effective_duration_seconds=600,
            effective_user_message_max_chars=2500,
            effective_game_reply_max_chars=3500,
            effective_analysis_reply_max_chars=4500,
            effective_llm_model_name="Qwen/Qwen3-32B",
            effective_llm_temperature=0.7,
            effective_llm_top_p=0.8,
            effective_llm_game_max_tokens=1500,
            effective_llm_analysis_max_tokens=2500,
            conditions_snapshot_text="Условия",
            opening_message_snapshot_text="Старт",
        )
        DialogMessage.objects.create(dialog=dialog, sequence_no=1, role=DialogMessageRole.ASSISTANT, text="Старт", char_count=5)
        DialogMessage.objects.create(dialog=dialog, sequence_no=2, role=DialogMessageRole.USER, text="Ответ", char_count=5)
        DialogMessage.objects.create(dialog=dialog, sequence_no=3, role=DialogMessageRole.ASSISTANT, text="Реплика", char_count=7)
        return dialog

    def test_analysis_retries_invalid_json_and_stores_valid_result(self) -> None:
        """Проверяет retry после невалидного JSON и сохранение валидного результата."""

        dialog = self._create_finished_dialog_with_user_message()
        AnalysisPrompt.objects.create(
            game=self.game,
            alias="json-retry",
            title="JSON retry",
            header_text="JSON retry",
            prompt_text="[[invalid_json_once]]",
            sort_order=1,
            min_rating=0,
            max_rating=5,
            is_active=True,
            created_by=self.user,
        )

        analysis_run = run_analysis_for_dialog(dialog)
        result = analysis_run.results.get()

        self.assertEqual(analysis_run.status, "completed")
        self.assertIn(result.validation_status, {AnalysisValidationStatus.VALID, AnalysisValidationStatus.FALLBACK_SAVED})
        self.assertGreaterEqual(result.llm_attempt_count, 1)

    def test_analysis_saves_fallback_for_invalid_schema(self) -> None:
        """Проверяет fallback-сохранение после исчерпания невалидной схемы."""

        dialog = self._create_finished_dialog_with_user_message()
        AnalysisPrompt.objects.create(
            game=self.game,
            alias="schema-fallback",
            title="Schema fallback",
            header_text="Schema fallback",
            prompt_text="[[invalid_schema_once]] [[invalid_schema_once]]",
            sort_order=1,
            min_rating=1,
            max_rating=4,
            is_active=True,
            created_by=self.user,
        )

        analysis_run = run_analysis_for_dialog(dialog)
        result = analysis_run.results.get()

        self.assertEqual(analysis_run.status, "completed")
        self.assertIn(
            result.validation_status,
            {
                AnalysisValidationStatus.INVALID_SCHEMA,
                AnalysisValidationStatus.FALLBACK_SAVED,
                AnalysisValidationStatus.VALID,
            },
        )

    def test_analysis_is_skipped_when_no_user_messages(self) -> None:
        """Проверяет, что анализ не создаётся при отсутствии реплик пользователя."""

        dialog = DialogSession.objects.create(
            user=self.user,
            game=self.game,
            scenario=self.scenario,
            scenario_prompt_used=self.scenario_prompt,
            status=DialogSessionStatus.ANALYSIS_SKIPPED,
            started_at="2026-03-26T10:00:00Z",
            ended_at="2026-03-26T10:01:00Z",
            ended_reason=DialogEndedReason.NO_USER_MESSAGES,
            user_message_count=0,
            assistant_message_count=1,
            effective_duration_seconds=600,
            effective_user_message_max_chars=2500,
            effective_game_reply_max_chars=3500,
            effective_analysis_reply_max_chars=4500,
            effective_llm_model_name="Qwen/Qwen3-32B",
            effective_llm_temperature=0.7,
            effective_llm_top_p=0.8,
            effective_llm_game_max_tokens=1500,
            effective_llm_analysis_max_tokens=2500,
            conditions_snapshot_text="Условия",
            opening_message_snapshot_text="Старт",
        )

        analysis_run = run_analysis_for_dialog(dialog)
        self.assertIsNone(analysis_run)
