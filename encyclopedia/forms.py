"""Формы энциклопедии для административного редактирования статей."""

from django import forms

from encyclopedia.models import EncyclopediaArticle


class EncyclopediaArticleAdminForm(forms.ModelForm):
    """Форма админки для управления статьями энциклопедии.

    Форма добавляет явный флаг перегенерации summary, который позволяет
    администратору и суперадминистратору обновить краткое описание
    на основе текущего заголовка и текста статьи.
    """

    regenerate_summary = forms.BooleanField(
        required=False,
        label="Перегенерировать краткое описание",
        help_text="Если включено, summary будет сгенерирован заново через сервис LLM/fallback.",
    )

    class Meta:
        """Мета-настройки состава и подсказок формы."""

        model = EncyclopediaArticle
        fields = "__all__"
        help_texts = {
            "body": "Лимит поля — максимум 5000 символов.",
        }

    def save(self, commit: bool = True) -> EncyclopediaArticle:
        """Сохраняет объект статьи с учётом флага регенерации summary.

        :param commit: Признак немедленного сохранения в БД.
        :return: Сохранённый или подготовленный экземпляр статьи.
        """
        instance = super().save(commit=False)
        if self.cleaned_data.get("regenerate_summary", False):
            instance.ensure_summary(force_regenerate=True)
        if commit:
            instance.save()
            self.save_m2m()
        return instance
