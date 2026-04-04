"""Начальная миграция приложения dialogs."""

import django.db.models.deletion
from django.db import migrations, models
from django.db.models import Q
import uuid


class Migration(migrations.Migration):
    """Создаёт таблицы диалоговых сессий и сообщений."""

    initial = True

    dependencies = [
        ("accounts", "0001_initial"),
        ("content", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="DialogSession",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("public_id", models.UUIDField(default=uuid.uuid4, editable=False, unique=True, verbose_name="Публичный ID")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="Создано")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="Обновлено")),
                ("status", models.CharField(choices=[("active", "Активный"), ("finished", "Завершён"), ("aborted", "Прерван"), ("analysis_skipped", "Анализ пропущен")], default="active", max_length=32, verbose_name="Статус")),
                ("started_at", models.DateTimeField(verbose_name="Начат")),
                ("ended_at", models.DateTimeField(blank=True, null=True, verbose_name="Завершён")),
                ("ended_reason", models.CharField(blank=True, choices=[("manual_feedback", "Кнопка обратной связи"), ("timeout", "Истёк таймер"), ("page_leave", "Покинута страница"), ("inactive_timeout", "Серверный таймаут неактивности"), ("no_user_messages", "Нет пользовательских сообщений")], max_length=64, verbose_name="Причина завершения")),
                ("user_message_count", models.PositiveIntegerField(default=0, verbose_name="Сообщений пользователя")),
                ("assistant_message_count", models.PositiveIntegerField(default=0, verbose_name="Сообщений ассистента")),
                ("effective_duration_seconds", models.PositiveIntegerField(verbose_name="Таймер (сек)")),
                ("effective_user_message_max_chars", models.PositiveIntegerField(verbose_name="Лимит пользовательского сообщения")),
                ("effective_game_reply_max_chars", models.PositiveIntegerField(verbose_name="Лимит игрового ответа")),
                ("effective_analysis_reply_max_chars", models.PositiveIntegerField(verbose_name="Лимит аналитического ответа")),
                ("effective_llm_model_name", models.CharField(max_length=255, verbose_name="Модель LLM")),
                ("effective_llm_temperature", models.DecimalField(decimal_places=2, max_digits=4, verbose_name="Temperature")),
                ("effective_llm_top_p", models.DecimalField(decimal_places=2, max_digits=4, verbose_name="Top-p")),
                ("effective_llm_game_max_tokens", models.PositiveIntegerField(verbose_name="Max tokens (игра)")),
                ("effective_llm_analysis_max_tokens", models.PositiveIntegerField(verbose_name="Max tokens (анализ)")),
                ("conditions_snapshot_text", models.TextField(verbose_name="Снимок условий")),
                ("opening_message_snapshot_text", models.TextField(verbose_name="Снимок стартовой реплики")),
                ("last_client_activity_at", models.DateTimeField(blank=True, null=True, verbose_name="Последняя активность клиента")),
                ("client_aborted_at", models.DateTimeField(blank=True, null=True, verbose_name="Клиент сообщил о выходе")),
                ("game", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="dialog_sessions", to="content.game", verbose_name="Игра")),
                ("scenario", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="dialog_sessions", to="content.scenario", verbose_name="Сценарий")),
                ("scenario_prompt_used", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="dialog_sessions", to="content.scenarioprompt", verbose_name="Использованный игровой промт")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="dialog_sessions", to="accounts.user", verbose_name="Пользователь")),
            ],
            options={"verbose_name": "Диалоговая сессия", "verbose_name_plural": "Диалоговые сессии", "ordering": ["-started_at"]},
        ),
        migrations.CreateModel(
            name="DialogMessage",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("sequence_no", models.PositiveIntegerField(verbose_name="Порядковый номер")),
                ("role", models.CharField(choices=[("assistant", "Ассистент"), ("user", "Пользователь")], max_length=32, verbose_name="Роль")),
                ("text", models.TextField(verbose_name="Текст")),
                ("char_count", models.PositiveIntegerField(verbose_name="Количество символов")),
                ("llm_request_id", models.CharField(blank=True, max_length=255, verbose_name="ID LLM-запроса")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="Создано")),
                ("dialog", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="messages", to="dialogs.dialogsession", verbose_name="Диалог")),
            ],
            options={"verbose_name": "Сообщение диалога", "verbose_name_plural": "Сообщения диалога", "ordering": ["dialog", "sequence_no"]},
        ),
        migrations.AddConstraint(
            model_name="dialogsession",
            constraint=models.UniqueConstraint(condition=Q(("status", "active")), fields=("user",), name="dialogs_single_active_session_per_user"),
        ),
        migrations.AddIndex(
            model_name="dialogsession",
            index=models.Index(fields=["user", "status"], name="dlg_sess_user_status_idx"),
        ),
        migrations.AddIndex(
            model_name="dialogsession",
            index=models.Index(fields=["game"], name="dialogs_session_game_idx"),
        ),
        migrations.AddIndex(
            model_name="dialogsession",
            index=models.Index(fields=["scenario"], name="dialogs_session_scenario_idx"),
        ),
        migrations.AddIndex(
            model_name="dialogsession",
            index=models.Index(fields=["started_at"], name="dialogs_session_started_idx"),
        ),
        migrations.AddConstraint(
            model_name="dialogmessage",
            constraint=models.UniqueConstraint(fields=("dialog", "sequence_no"), name="dialogs_message_unique_sequence_per_dialog"),
        ),
        migrations.AddIndex(
            model_name="dialogmessage",
            index=models.Index(fields=["dialog", "sequence_no"], name="dialogs_message_dialog_seq_idx"),
        ),
    ]
