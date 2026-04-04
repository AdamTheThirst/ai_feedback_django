"""ORM-модели раздела энциклопедии."""

from __future__ import annotations

import re

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.template.defaultfilters import slugify

from encyclopedia.services import SummaryGenerationInput, generate_summary, transliterate_to_slug_source


def validate_no_html_tags(value: str) -> None:
    """Проверяет, что строковое поле не содержит HTML-тегов.

    Валидатор применяется к заголовку статьи, где по требованиям
    допускается только чистый текст без тегов и форматирования.

    :param value: Проверяемое текстовое значение.
    :raises ValidationError: Если обнаружены HTML-теги вида `<...>`.
    """
    if re.search(r"<[^>]+>", value or ""):
        raise ValidationError("Поле не должно содержать HTML-теги.")


def validate_summary_text(value: str) -> None:
    """Проверяет ограничения для поля summary.

    В контексте проекта summary должен быть обычным текстом без HTML,
    markdown-разметки и пустых бессодержательных формулировок.

    :param value: Текст краткого описания.
    :raises ValidationError: При нарушении формата или длины.
    """
    text = (value or "").strip()
    if len(text) < 50 or len(text) > 255:
        raise ValidationError("Summary должен содержать от 50 до 255 символов.")
    if re.search(r"<[^>]+>", text):
        raise ValidationError("Summary не должен содержать HTML.")
    if re.search(r"(^|\s)[\-*#]{1,3}(\s|$)", text):
        raise ValidationError("Summary не должен содержать markdown-списки.")


class EncyclopediaArticle(models.Model):
    """Статья энциклопедии с публикацией и служебными полями аудита.

    Модель используется одновременно в пользовательском разделе
    энциклопедии и в административном интерфейсе управления контентом.

    Поля соответствуют требованиям ТЗ: заголовок, текст, summary,
    признак публикации, стабильный slug и служебные поля автора/дат.
    """

    title = models.CharField(
        max_length=128,
        verbose_name="Заголовок",
        validators=[validate_no_html_tags],
    )
    slug = models.SlugField(max_length=150, unique=True, verbose_name="Slug")
    body = models.TextField(max_length=5000, verbose_name="Текст статьи")
    summary = models.CharField(
        max_length=255,
        verbose_name="Краткое описание",
        validators=[validate_summary_text],
    )
    is_published = models.BooleanField(default=False, verbose_name="Опубликовано")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_encyclopedia_articles",
        verbose_name="Создал",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="updated_encyclopedia_articles",
        verbose_name="Обновил",
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Создано")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Обновлено")

    class Meta:
        """Мета-настройки модели для админки и SQL-таблицы."""

        db_table = "encyclopedia_article"
        verbose_name = "Статья энциклопедии"
        verbose_name_plural = "Статьи энциклопедии"

    def __str__(self) -> str:
        """Возвращает человекочитаемое название записи.

        :return: Заголовок статьи.
        """
        return self.title

    def clean(self) -> None:
        """Выполняет дополнительную серверную валидацию полей статьи.

        Проверяет ограничения по длине текста статьи и нормализует
        summary перед сохранением.

        :raises ValidationError: При нарушении бизнес-ограничений.
        """
        super().clean()
        if len(self.body or "") > 5000:
            raise ValidationError({"body": "Текст статьи не должен превышать 5000 символов."})
        validate_no_html_tags(self.title)
        validate_summary_text(self.summary)

    def _generate_unique_slug(self) -> str:
        """Генерирует уникальный slug из заголовка статьи.

        Slug формируется один раз при создании записи и затем
        не пересчитывается автоматически при изменении заголовка.

        :return: Уникальный slug для URL статьи.
        """
        base = slugify(transliterate_to_slug_source(self.title)) or "article"
        candidate = base
        index = 2
        while EncyclopediaArticle.objects.filter(slug=candidate).exclude(pk=self.pk).exists():
            candidate = f"{base}-{index}"
            index += 1
        return candidate

    def ensure_summary(self, force_regenerate: bool = False) -> None:
        """Обеспечивает заполнение поля summary по правилам проекта.

        Метод может вызываться из админ-формы для явной регенерации,
        а также из `save`, когда поле summary пустое.

        :param force_regenerate: Признак обязательной перегенерации.
        """
        if force_regenerate or not self.summary:
            self.summary = generate_summary(SummaryGenerationInput(title=self.title, body=self.body))

    def save(self, *args, **kwargs) -> None:
        """Сохраняет статью с автогенерацией slug и summary.

        Перед записью в БД метод:
        - генерирует slug для новых статей;
        - заполняет summary, если оно пустое;
        - запускает полную валидацию модели.

        :param args: Позиционные аргументы ORM-сохранения.
        :param kwargs: Именованные аргументы ORM-сохранения.
        :raises ValidationError: При невалидных данных модели.
        """
        if not self.slug:
            self.slug = self._generate_unique_slug()
        self.ensure_summary(force_regenerate=False)
        self.full_clean()
        super().save(*args, **kwargs)
