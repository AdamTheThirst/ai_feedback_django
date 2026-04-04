"""Начальная миграция приложения analysis."""

import django.db.models.deletion
from django.db import migrations, models
from django.db.models import Q
import uuid


class Migration(migrations.Migration):
    """Создаёт таблицы запуска анализа и результатов критериев."""

    initial = True

    dependencies = [
        ("content", "0001_initial"),
        ("dialogs", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="AnalysisRun",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("public_id", models.UUIDField(default=uuid.uuid4, editable=False, unique=True, verbose_name="Публичный ID")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="Создано")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="Обновлено")),
                ("status", models.CharField(choices=[("pending", "Ожидает"), ("running", "Выполняется"), ("completed", "Завершён"), ("failed", "Ошибка"), ("skipped", "Пропущен")], default="pending", max_length=32, verbose_name="Статус")),
                ("started_at", models.DateTimeField(verbose_name="Запущен")),
                ("finished_at", models.DateTimeField(blank=True, null=True, verbose_name="Завершён")),
                ("llm_attempt_count", models.PositiveIntegerField(default=0, verbose_name="Количество LLM-попыток")),
                ("error_code", models.CharField(blank=True, max_length=128, verbose_name="Код ошибки")),
                ("error_message", models.TextField(blank=True, verbose_name="Текст ошибки")),
                ("dialog", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="analysis_run", to="dialogs.dialogsession", verbose_name="Диалог")),
            ],
            options={"verbose_name": "Запуск анализа", "verbose_name_plural": "Запуски анализа", "ordering": ["-started_at"]},
        ),
        migrations.CreateModel(
            name="AnalysisResult",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="Создано")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="Обновлено")),
                ("sort_order_snapshot", models.PositiveIntegerField(verbose_name="Порядок (snapshot)")),
                ("alias_snapshot", models.SlugField(verbose_name="Alias (snapshot)")),
                ("title_snapshot", models.CharField(max_length=255, verbose_name="Название (snapshot)")),
                ("header_snapshot_text", models.CharField(max_length=255, verbose_name="Заголовок (snapshot)")),
                ("comment_snapshot_text", models.TextField(blank=True, verbose_name="Комментарий (snapshot)")),
                ("rating", models.SmallIntegerField(verbose_name="Балл")),
                ("rating_min", models.SmallIntegerField(verbose_name="Минимум шкалы")),
                ("rating_max", models.SmallIntegerField(verbose_name="Максимум шкалы")),
                ("analysis_text", models.TextField(verbose_name="Текст анализа")),
                ("raw_llm_response_text", models.TextField(blank=True, verbose_name="Сырой ответ LLM")),
                ("parsed_json_snapshot", models.JSONField(blank=True, null=True, verbose_name="JSON snapshot")),
                ("validation_status", models.CharField(choices=[("valid", "Валидно"), ("invalid_json", "Невалидный JSON"), ("invalid_schema", "Невалидная схема"), ("fallback_saved", "Сохранён fallback")], default="valid", max_length=32, verbose_name="Статус валидации")),
                ("validation_error_message", models.TextField(blank=True, verbose_name="Ошибка валидации")),
                ("llm_attempt_count", models.PositiveIntegerField(default=1, verbose_name="Попыток по критерию")),
                ("analysis_prompt", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="analysis_results", to="content.analysisprompt", verbose_name="Аналитический промт")),
                ("analysis_run", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="results", to="analysis.analysisrun", verbose_name="Запуск анализа")),
            ],
            options={"verbose_name": "Результат анализа", "verbose_name_plural": "Результаты анализа", "ordering": ["analysis_run", "sort_order_snapshot", "id"]},
        ),
        migrations.AddConstraint(
            model_name="analysisresult",
            constraint=models.UniqueConstraint(fields=("analysis_run", "analysis_prompt"), name="analysis_result_unique_run_prompt"),
        ),
        migrations.AddConstraint(
            model_name="analysisresult",
            constraint=models.CheckConstraint(check=Q(("rating__gte", models.F("rating_min")), ("rating__lte", models.F("rating_max"))), name="analysis_result_rating_in_range"),
        ),
        migrations.AddIndex(
            model_name="analysisresult",
            index=models.Index(fields=["analysis_run", "sort_order_snapshot"], name="analysis_result_run_sort_idx"),
        ),
    ]
