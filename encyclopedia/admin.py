"""Регистрация модели энциклопедии в административном интерфейсе Django."""

from django.contrib import admin
from django.http import HttpRequest

from encyclopedia.forms import EncyclopediaArticleAdminForm
from encyclopedia.models import EncyclopediaArticle


@admin.register(EncyclopediaArticle)
class EncyclopediaArticleAdmin(admin.ModelAdmin):
    """Административный интерфейс управления статьями энциклопедии.

    Интерфейс используется администраторами и суперадминистраторами
    для полного CRUD-управления материалами раздела.
    """

    form = EncyclopediaArticleAdminForm
    list_display = ("title", "is_published", "created_by", "updated_by", "updated_at")
    list_filter = ("is_published", "created_at", "updated_at")
    search_fields = ("title", "body", "summary")
    prepopulated_fields: dict[str, tuple[str, ...]] = {}

    def save_model(
        self,
        request: HttpRequest,
        obj: EncyclopediaArticle,
        form: EncyclopediaArticleAdminForm,
        change: bool,
    ) -> None:
        """Заполняет служебные поля автора перед сохранением модели.

        :param request: HTTP-запрос администратора.
        :param obj: Сохраняемый экземпляр статьи.
        :param form: Валидированная форма админки.
        :param change: Признак редактирования существующей записи.
        """
        if not obj.created_by_id:
            obj.created_by = request.user
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)
