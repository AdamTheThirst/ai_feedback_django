"""Начальная миграция приложения auditlog."""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    """Создаёт таблицу технического журнала событий."""

    initial = True

    dependencies = [
        ("accounts", "0001_initial"),
        ("dialogs", "0001_initial"),
        ("analysis", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="AuditLogEntry",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="Создано")),
                ("level", models.CharField(choices=[("debug", "Debug"), ("info", "Info"), ("warning", "Warning"), ("error", "Error"), ("critical", "Critical")], max_length=16, verbose_name="Уровень")),
                ("event_type", models.CharField(max_length=128, verbose_name="Тип события")),
                ("message", models.TextField(verbose_name="Сообщение")),
                ("object_type", models.CharField(blank=True, max_length=128, verbose_name="Тип объекта")),
                ("object_id", models.CharField(blank=True, max_length=128, verbose_name="ID объекта")),
                ("context_json", models.JSONField(blank=True, null=True, verbose_name="JSON-контекст")),
                ("traceback_text", models.TextField(blank=True, verbose_name="Traceback")),
                ("actor_user", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="audit_log_entries", to="accounts.user", verbose_name="Пользователь-инициатор")),
                ("analysis_run", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="audit_log_entries", to="analysis.analysisrun", verbose_name="Запуск анализа")),
                ("dialog", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="audit_log_entries", to="dialogs.dialogsession", verbose_name="Диалог")),
            ],
            options={"verbose_name": "Запись аудит-лога", "verbose_name_plural": "Аудит-лог", "ordering": ["-created_at", "-id"]},
        ),
        migrations.AddIndex(
            model_name="auditlogentry",
            index=models.Index(fields=["level", "created_at"], name="auditlog_level_created_idx"),
        ),
        migrations.AddIndex(
            model_name="auditlogentry",
            index=models.Index(fields=["event_type", "created_at"], name="auditlog_event_created_idx"),
        ),
    ]
