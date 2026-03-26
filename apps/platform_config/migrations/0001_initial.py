"""Начальная миграция приложения platform_config."""

import django.core.validators
import django.db.models.deletion
from django.db import migrations, models
from django.db.models import Q


class Migration(migrations.Migration):
    """Создаёт таблицы глобальных настроек и UI-текстов."""

    initial = True

    dependencies = [
        ("accounts", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="PlatformSettings",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="Создано")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="Обновлено")),
                ("is_active", models.BooleanField(default=True, verbose_name="Активна")),
                ("default_dialog_duration_minutes", models.PositiveSmallIntegerField(default=10, help_text="Глобальная длительность диалога в минутах.", validators=[django.core.validators.MinValueValidator(1), django.core.validators.MaxValueValidator(120)], verbose_name="Длительность диалога по умолчанию (мин)")),
                ("user_timer_min_minutes", models.PositiveSmallIntegerField(default=5, help_text="Нижняя граница будущей пользовательской настройки таймера.", validators=[django.core.validators.MinValueValidator(1), django.core.validators.MaxValueValidator(120)], verbose_name="Минимум пользовательского таймера (мин)")),
                ("user_timer_max_minutes", models.PositiveSmallIntegerField(default=20, help_text="Верхняя граница будущей пользовательской настройки таймера.", validators=[django.core.validators.MinValueValidator(1), django.core.validators.MaxValueValidator(120)], verbose_name="Максимум пользовательского таймера (мин)")),
                ("default_show_timer", models.BooleanField(default=True, verbose_name="Показывать таймер")),
                ("max_user_message_chars", models.PositiveIntegerField(default=2500, help_text="Лимит длины пользовательского сообщения.", validators=[django.core.validators.MinValueValidator(1), django.core.validators.MaxValueValidator(20000)], verbose_name="Лимит сообщения пользователя")),
                ("max_game_reply_chars", models.PositiveIntegerField(default=3500, help_text="Лимит длины игрового ответа ассистента.", validators=[django.core.validators.MinValueValidator(1), django.core.validators.MaxValueValidator(20000)], verbose_name="Лимит игрового ответа")),
                ("max_analysis_reply_chars", models.PositiveIntegerField(default=4500, help_text="Лимит длины аналитического ответа.", validators=[django.core.validators.MinValueValidator(1), django.core.validators.MaxValueValidator(30000)], verbose_name="Лимит аналитического ответа")),
                ("llm_base_url", models.URLField(verbose_name="LLM base URL")),
                ("llm_api_key", models.CharField(blank=True, max_length=255, verbose_name="LLM API ключ")),
                ("llm_model_name", models.CharField(default="Qwen/Qwen3-32B", max_length=255, verbose_name="LLM модель")),
                ("llm_temperature", models.DecimalField(decimal_places=2, default=0.7, max_digits=3, validators=[django.core.validators.MinValueValidator(0), django.core.validators.MaxValueValidator(2)], verbose_name="LLM temperature")),
                ("llm_top_p", models.DecimalField(decimal_places=2, default=0.8, max_digits=3, validators=[django.core.validators.MinValueValidator(0), django.core.validators.MaxValueValidator(1)], verbose_name="LLM top-p")),
                ("llm_game_max_tokens", models.PositiveIntegerField(default=1500, validators=[django.core.validators.MinValueValidator(1), django.core.validators.MaxValueValidator(32768)], verbose_name="Max tokens (игра)")),
                ("llm_analysis_max_tokens", models.PositiveIntegerField(default=2500, validators=[django.core.validators.MinValueValidator(1), django.core.validators.MaxValueValidator(32768)], verbose_name="Max tokens (анализ)")),
                ("client_abort_grace_seconds", models.PositiveSmallIntegerField(default=15, validators=[django.core.validators.MinValueValidator(1), django.core.validators.MaxValueValidator(600)], verbose_name="Окно ожидания после client abort (сек)")),
            ],
            options={"verbose_name": "Глобальные настройки платформы", "verbose_name_plural": "Глобальные настройки платформы"},
        ),
        migrations.CreateModel(
            name="UIText",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="Создано")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="Обновлено")),
                ("is_archived", models.BooleanField(default=False, verbose_name="В архиве")),
                ("archived_at", models.DateTimeField(blank=True, null=True, verbose_name="Архивировано")),
                ("key", models.SlugField(unique=True, verbose_name="Ключ")),
                ("title", models.CharField(max_length=255, verbose_name="Название")),
                ("text_value", models.TextField(verbose_name="Текст")),
                ("description", models.TextField(blank=True, verbose_name="Описание")),
                ("updated_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="updated_ui_texts", to="accounts.user", verbose_name="Обновил")),
            ],
            options={"verbose_name": "UI-текст", "verbose_name_plural": "UI-тексты", "ordering": ["key"]},
        ),
        migrations.AddConstraint(
            model_name="platformsettings",
            constraint=models.UniqueConstraint(condition=Q(("is_active", True)), fields=("is_active",), name="platform_config_single_active_settings"),
        ),
        migrations.AddConstraint(
            model_name="platformsettings",
            constraint=models.CheckConstraint(check=Q(("user_timer_min_minutes__lte", models.F("user_timer_max_minutes"))), name="platform_config_timer_min_lte_max"),
        ),
    ]
