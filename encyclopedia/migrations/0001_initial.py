"""Начальная миграция для создания таблицы статей энциклопедии."""

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion

import encyclopedia.models


class Migration(migrations.Migration):
    """Создаёт основную таблицу `encyclopedia_article` и связи с пользователем."""

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="EncyclopediaArticle",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(max_length=128, validators=[encyclopedia.models.validate_no_html_tags], verbose_name="Заголовок")),
                ("slug", models.SlugField(max_length=150, unique=True, verbose_name="Slug")),
                ("body", models.TextField(max_length=5000, verbose_name="Текст статьи")),
                ("summary", models.CharField(max_length=255, validators=[encyclopedia.models.validate_summary_text], verbose_name="Краткое описание")),
                ("is_published", models.BooleanField(default=False, verbose_name="Опубликовано")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="Создано")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="Обновлено")),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="created_encyclopedia_articles",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Создал",
                    ),
                ),
                (
                    "updated_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="updated_encyclopedia_articles",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Обновил",
                    ),
                ),
            ],
            options={
                "verbose_name": "Статья энциклопедии",
                "verbose_name_plural": "Статьи энциклопедии",
                "db_table": "encyclopedia_article",
            },
        ),
    ]
