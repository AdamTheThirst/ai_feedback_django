"""Представления внутренней административной панели для контентных CRUD-операций."""

from typing import Any

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db.models import QuerySet
from django.http import HttpRequest, HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views import View
from django.views.generic import CreateView, ListView, UpdateView

from apps.adminpanel.forms import (
    AnalysisPromptForm,
    GameForm,
    ScenarioForm,
    ScenarioMediaAssetForm,
    ScenarioPromptForm,
    SystemPromptForm,
    UserCreateForm,
)
from apps.adminpanel.services import (
    build_backoffice_stats,
    filter_owned_queryset,
    user_can_access_backoffice,
    user_can_manage_object,
)
from apps.analysis.models import AnalysisRun
from apps.accounts.models import User
from apps.auditlog.models import AuditLogEntry
from apps.content.models import (
    AnalysisPrompt,
    Game,
    Scenario,
    ScenarioMediaAsset,
    ScenarioPrompt,
    SystemPrompt,
)
from apps.dialogs.models import DialogSession


class BackofficeAccessMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Проверяет доступ пользователя к внутренней административной панели.

    Контекст использования:
        Используется всеми view бэкофиса для изоляции административных маршрутов
        от обычных пользователей.

    Параметры:
        Применяется как mixin в class-based views.

    Возвращаемое значение:
        Разрешает выполнение view только при корректной роли пользователя.

    Исключения и особые случаи:
        При недостатке прав возвращает ``403 Forbidden``.

    Побочные эффекты:
        Побочные эффекты отсутствуют.
    """

    def test_func(self) -> bool:
        """Проверяет, имеет ли пользователь административную роль.

        Контекст использования:
            Вызывается Django ``UserPassesTestMixin`` перед обработкой запроса.

        Параметры:
            Параметры отсутствуют.

        Возвращаемое значение:
            ``True`` при наличии прав, иначе ``False``.

        Исключения и особые случаи:
            Исключения не предусмотрены.

        Побочные эффекты:
            Побочные эффекты отсутствуют.
        """

        return user_can_access_backoffice(self.request.user)

    def handle_no_permission(self) -> HttpResponse:
        """Возвращает ответ при отсутствии доступа к бэкофису.

        Контекст использования:
            Используется для явного ответа ``403`` авторизованным без нужной роли.

        Параметры:
            Параметры отсутствуют.

        Возвращаемое значение:
            ``HttpResponseForbidden`` или стандартное поведение для анонимов.

        Исключения и особые случаи:
            Для неавторизованного пользователя оставляет редирект на login.

        Побочные эффекты:
            Побочные эффекты отсутствуют.
        """

        if self.request.user.is_authenticated:
            return HttpResponseForbidden("Недостаточно прав для доступа к админ-панели.")
        return super().handle_no_permission()


class SuperadminOnlyMixin(BackofficeAccessMixin):
    """Разрешает доступ к view только пользователю роли superadmin.

    Контекст использования:
        Нужен для раздела управления пользователями и других операций,
        которые по бизнес-правилам доступны только супер-администратору.

    Параметры:
        Используется как mixin в class-based views.

    Возвращаемое значение:
        ``True`` только для аутентифицированного superadmin.

    Исключения и особые случаи:
        При недостатке прав возвращает ``403`` через базовый mixin.

    Побочные эффекты:
        Побочные эффекты отсутствуют.
    """

    def test_func(self) -> bool:
        """Проверяет, что пользователь имеет роль superadmin.

        Контекст использования:
            Вызывается перед доступом к чувствительным административным view.

        Параметры:
            Параметры отсутствуют.

        Возвращаемое значение:
            ``True`` для superadmin, иначе ``False``.

        Исключения и особые случаи:
            Особые исключения отсутствуют.

        Побочные эффекты:
            Побочные эффекты отсутствуют.
        """

        return bool(self.request.user.is_authenticated and self.request.user.role == "superadmin")


class BackofficeBaseListView(BackofficeAccessMixin, ListView):
    """Базовый список бэкофиса с фильтрацией по владению для администратора."""

    template_name = "adminpanel/object_list.html"
    context_object_name = "object_list"
    section_title = "Список"

    def get_queryset(self) -> QuerySet:
        """Возвращает queryset с учётом роли и владения объектами.

        Контекст использования:
            Единая точка реализации правила «администратор видит только свои объекты».

        Параметры:
            Параметры отсутствуют.

        Возвращаемое значение:
            Отфильтрованный queryset модели ``self.model``.

        Исключения и особые случаи:
            Для моделей без ``created_by`` фильтрация по owner пропускается.

        Побочные эффекты:
            Побочные эффекты отсутствуют.
        """

        queryset = super().get_queryset().order_by("-id")
        if hasattr(self.model, "created_by"):
            return filter_owned_queryset(queryset, self.request.user)
        if self.model is ScenarioMediaAsset and self.request.user.role == "admin":
            return queryset.filter(uploaded_by=self.request.user)
        return queryset

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        """Добавляет заголовки и служебные ссылки в контекст списка.

        Контекст использования:
            Обеспечивает единообразный layout для всех list-страниц контента.

        Параметры:
            **kwargs: Дополнительный контекст базового класса ``ListView``.

        Возвращаемое значение:
            Расширенный словарь контекста шаблона.

        Исключения и особые случаи:
            Особые исключения отсутствуют.

        Побочные эффекты:
            Побочные эффекты отсутствуют.
        """

        context = super().get_context_data(**kwargs)
        context["section_title"] = self.section_title
        context["create_url"] = self.create_url
        context["update_url_name"] = self.update_url_name
        context["archive_url_name"] = self.archive_url_name
        return context


class BackofficeBaseCreateView(BackofficeAccessMixin, CreateView):
    """Базовое создание контентного объекта с назначением владельца записи."""

    template_name = "adminpanel/object_form.html"

    def get_form_kwargs(self) -> dict[str, Any]:
        """Передаёт текущего пользователя в форму бэкофиса.

        Контекст использования:
            Нужно для ролевой фильтрации связанных queryset в ModelForm.

        Параметры:
            Параметры отсутствуют.

        Возвращаемое значение:
            Словарь аргументов для конструктора формы.

        Исключения и особые случаи:
            Исключения не ожидаются.

        Побочные эффекты:
            Побочные эффекты отсутствуют.
        """

        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def form_valid(self, form):
        """Устанавливает владельца/загрузчика и сохраняет объект.

        Контекст использования:
            Вызывается при успешной валидации формы создания.

        Параметры:
            form: Валидированная форма ``ModelForm``.

        Возвращаемое значение:
            HTTP-ответ базового ``CreateView`` после сохранения.

        Исключения и особые случаи:
            Исключения обработки валидации остаются на уровне формы.

        Побочные эффекты:
            Создаёт новую запись модели в БД.
        """

        if hasattr(form.instance, "created_by"):
            form.instance.created_by = self.request.user
        if hasattr(form.instance, "uploaded_by"):
            form.instance.uploaded_by = self.request.user
        messages.success(self.request, "Запись успешно создана.")
        return super().form_valid(form)


class BackofficeBaseUpdateView(BackofficeAccessMixin, UpdateView):
    """Базовое редактирование контентного объекта с проверкой владения."""

    template_name = "adminpanel/object_form.html"

    def get_form_kwargs(self) -> dict[str, Any]:
        """Передаёт текущего пользователя в форму редактирования.

        Контекст использования:
            Нужен для корректной фильтрации связанных объектов в форме.

        Параметры:
            Параметры отсутствуют.

        Возвращаемое значение:
            Словарь аргументов для формы.

        Исключения и особые случаи:
            Исключения не ожидаются.

        Побочные эффекты:
            Побочные эффекты отсутствуют.
        """

        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def dispatch(self, request: HttpRequest, *args, **kwargs) -> HttpResponse:
        """Проверяет доступ к объекту перед редактированием.

        Контекст использования:
            Защищает update-операцию от редактирования чужих объектов админом.

        Параметры:
            request: Входящий HTTP-запрос.
            *args: Позиционные аргументы маршрута.
            **kwargs: Именованные аргументы маршрута.

        Возвращаемое значение:
            ``403 Forbidden`` при отсутствии прав или обычный ответ view.

        Исключения и особые случаи:
            Исключения не ожидаются.

        Побочные эффекты:
            Побочные эффекты отсутствуют.
        """

        self.object = self.get_object()
        owner_field_name = "uploaded_by" if hasattr(self.object, "uploaded_by") else "created_by"
        if not user_can_manage_object(request.user, self.object, owner_field_name=owner_field_name):
            return HttpResponseForbidden("Недостаточно прав для изменения этого объекта.")
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        """Сохраняет изменения объекта и показывает сообщение об успехе.

        Контекст использования:
            Единая обработка успешного редактирования для контуров CRUD.

        Параметры:
            form: Валидированная форма изменения.

        Возвращаемое значение:
            HTTP-ответ базового ``UpdateView``.

        Исключения и особые случаи:
            Исключения валидации остаются на уровне формы.

        Побочные эффекты:
            Обновляет запись в БД.
        """

        messages.success(self.request, "Изменения сохранены.")
        return super().form_valid(form)


class BackofficeArchiveView(BackofficeAccessMixin, View):
    """Базовый архиватор контентных объектов с ролевой проверкой доступа."""

    model = None
    owner_field_name = "created_by"
    success_url_name = "adminpanel:dashboard"

    def post(self, request: HttpRequest, pk: int) -> HttpResponse:
        """Помечает запись архивной без физического удаления из БД.

        Контекст использования:
            Реализует политику soft-delete в административных CRUD-операциях.

        Параметры:
            request: HTTP-запрос.
            pk: Первичный ключ архивируемой записи.

        Возвращаемое значение:
            Redirect на список соответствующего раздела.

        Исключения и особые случаи:
            При недостатке прав возвращается ``403 Forbidden``.

        Побочные эффекты:
            Изменяет поля ``is_archived`` и ``archived_at`` объекта.
        """

        obj = get_object_or_404(self.model, pk=pk)
        if not user_can_manage_object(request.user, obj, owner_field_name=self.owner_field_name):
            return HttpResponseForbidden("Недостаточно прав для архивирования объекта.")
        obj.is_archived = True
        obj.archived_at = obj.archived_at or timezone.now()
        obj.save(update_fields=["is_archived", "archived_at", "updated_at"])
        messages.success(request, "Запись архивирована.")
        return redirect(self.success_url_name)


class DashboardView(BackofficeAccessMixin, View):
    """Отображает дашборд внутренней административной панели."""

    def get(self, request: HttpRequest) -> HttpResponse:
        """Собирает и рендерит статистику ключевых сущностей платформы.

        Контекст использования:
            Главная страница ``/backoffice/`` для быстрого обзора состояния.

        Параметры:
            request: HTTP-запрос администратора или супер-администратора.

        Возвращаемое значение:
            HTML-страница дашборда.

        Исключения и особые случаи:
            Исключения не ожидаются.

        Побочные эффекты:
            Выполняет несколько ``COUNT``-запросов к БД.
        """

        stats_map: dict[str, type] = {
            "games": Game,
            "scenarios": Scenario,
            "analysis_prompts": AnalysisPrompt,
            "system_prompts": SystemPrompt,
            "media_assets": ScenarioMediaAsset,
            "dialogs": DialogSession,
            "analysis_runs": AnalysisRun,
            "audit_entries": AuditLogEntry,
        }
        if request.user.role == "superadmin":
            stats_map["users"] = User
        stats = build_backoffice_stats(stats_map)
        return render(request, "adminpanel/dashboard.html", {"stats": stats})


class UserListView(SuperadminOnlyMixin, ListView):
    """Список пользователей для управления супер-администратором.

    Контекст использования:
        Отдельный раздел бэкофиса, где супер-админ видит все учётные записи
        и может контролировать статус доступа пользователей.

    Параметры:
        Использует стандартные параметры ``ListView`` Django.

    Возвращаемое значение:
        HTML-страница с таблицей/списком пользователей.

    Исключения и особые случаи:
        Для ролей ниже ``superadmin`` доступ блокируется.

    Побочные эффекты:
        Побочные эффекты отсутствуют.
    """

    template_name = "adminpanel/user_list.html"
    context_object_name = "users"

    def get_queryset(self) -> QuerySet:
        """Возвращает полный список пользователей по убыванию ID.

        Контекст использования:
            Нужен для отображения последних созданных/обновлённых пользователей
            в разделе управления доступами.

        Параметры:
            Параметры отсутствуют.

        Возвращаемое значение:
            ``QuerySet`` модели ``User``.

        Исключения и особые случаи:
            Исключения не ожидаются.

        Побочные эффекты:
            Побочные эффекты отсутствуют.
        """

        return User.objects.order_by("-id")


class UserCreateView(SuperadminOnlyMixin, View):
    """Создаёт пользователя через форму супер-администратора.

    Контекст использования:
        Используется для ручного заведения новых пользователей в системе
        через внутренний бэкофис.

    Параметры:
        Принимает стандартные параметры ``View`` и данные формы POST.

    Возвращаемое значение:
        Страница формы или redirect на список пользователей после создания.

    Исключения и особые случаи:
        Ошибки валидации возвращаются пользователю на форме.

    Побочные эффекты:
        Создаёт нового пользователя в базе данных.
    """

    template_name = "adminpanel/user_form.html"

    def get(self, request: HttpRequest) -> HttpResponse:
        """Показывает форму создания пользователя.

        Контекст использования:
            Используется при открытии страницы «Создать пользователя».

        Параметры:
            request: HTTP-запрос супер-администратора.

        Возвращаемое значение:
            HTML-страница формы.

        Исключения и особые случаи:
            Исключения не ожидаются.

        Побочные эффекты:
            Побочные эффекты отсутствуют.
        """

        return render(request, self.template_name, {"form": UserCreateForm()})

    def post(self, request: HttpRequest) -> HttpResponse:
        """Создаёт пользователя при валидной форме.

        Контекст использования:
            Обрабатывает submit формы заведения новой учётной записи.

        Параметры:
            request: HTTP-запрос супер-администратора.

        Возвращаемое значение:
            Redirect на список пользователей или страница формы с ошибками.

        Исключения и особые случаи:
            Ошибки валидации остаются на уровне формы.

        Побочные эффекты:
            Создаёт запись ``User`` в БД.
        """

        form = UserCreateForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Пользователь создан.")
            return redirect("adminpanel:user_list")
        return render(request, self.template_name, {"form": form})


class UserToggleActiveView(SuperadminOnlyMixin, View):
    """Переключает активность пользователя (исключить/вернуть).

    Контекст использования:
        Реализует мягкое исключение из системы через ``is_active=False``
        и обратное восстановление без удаления исторических данных.

    Параметры:
        Принимает ``pk`` пользователя и HTTP POST-запрос супер-админа.

    Возвращаемое значение:
        Redirect на список пользователей.

    Исключения и особые случаи:
        Главный супер-администратор не может отключить сам себя.

    Побочные эффекты:
        Обновляет флаг активности пользователя в БД.
    """

    def post(self, request: HttpRequest, pk: int) -> HttpResponse:
        """Меняет флаг ``is_active`` выбранной учётной записи.

        Контекст использования:
            Реализует «исключение» пользователя без жёсткого удаления данных.

        Параметры:
            request: HTTP-запрос супер-администратора.
            pk: ID целевого пользователя.

        Возвращаемое значение:
            Redirect на список пользователей.

        Исключения и особые случаи:
            Нельзя отключить самого главного супер-админа.

        Побочные эффекты:
            Обновляет поле ``is_active`` в БД.
        """

        target_user = get_object_or_404(User, pk=pk)
        if target_user == request.user and target_user.is_primary_superadmin:
            messages.error(request, "Нельзя отключить главного супер-админа.")
            return redirect("adminpanel:user_list")
        target_user.is_active = not target_user.is_active
        target_user.save(update_fields=["is_active"])
        messages.success(request, "Статус пользователя обновлён.")
        return redirect("adminpanel:user_list")


class GameListView(BackofficeBaseListView):
    """Список игр в контурной административной панели."""

    model = Game
    section_title = "Игры"
    create_url = "adminpanel:game_create"
    update_url_name = "adminpanel:game_update"
    archive_url_name = "adminpanel:game_archive"


class GameCreateView(BackofficeBaseCreateView):
    """Создание игры через внутреннюю административную панель."""

    model = Game
    form_class = GameForm
    success_url = "/backoffice/games/"


class GameUpdateView(BackofficeBaseUpdateView):
    """Редактирование игры с проверкой прав владения."""

    model = Game
    form_class = GameForm
    success_url = "/backoffice/games/"


class GameArchiveView(BackofficeArchiveView):
    """Архивирование игры без физического удаления."""

    model = Game
    success_url_name = "adminpanel:game_list"


class ScenarioListView(BackofficeBaseListView):
    """Список сценариев с ролевой фильтрацией по владельцу."""

    model = Scenario
    section_title = "Сценарии"
    create_url = "adminpanel:scenario_create"
    update_url_name = "adminpanel:scenario_update"
    archive_url_name = "adminpanel:scenario_archive"


class ScenarioCreateView(BackofficeBaseCreateView):
    """Создание сценария через административную панель."""

    model = Scenario
    form_class = ScenarioForm
    success_url = "/backoffice/scenarios/"


class ScenarioUpdateView(BackofficeBaseUpdateView):
    """Редактирование сценария в пределах прав пользователя."""

    model = Scenario
    form_class = ScenarioForm
    success_url = "/backoffice/scenarios/"


class ScenarioArchiveView(BackofficeArchiveView):
    """Архивирование сценария через soft-delete политику."""

    model = Scenario
    success_url_name = "adminpanel:scenario_list"


class ScenarioPromptListView(BackofficeBaseListView):
    """Список игровых промтов сценариев."""

    model = ScenarioPrompt
    section_title = "Игровые промты"
    create_url = "adminpanel:scenario_prompt_create"
    update_url_name = "adminpanel:scenario_prompt_update"
    archive_url_name = "adminpanel:scenario_prompt_archive"


class ScenarioPromptCreateView(BackofficeBaseCreateView):
    """Создание игрового промта для сценария."""

    model = ScenarioPrompt
    form_class = ScenarioPromptForm
    success_url = "/backoffice/scenario-prompts/"


class ScenarioPromptUpdateView(BackofficeBaseUpdateView):
    """Редактирование игрового промта с учётом прав доступа."""

    model = ScenarioPrompt
    form_class = ScenarioPromptForm
    success_url = "/backoffice/scenario-prompts/"


class ScenarioPromptArchiveView(BackofficeArchiveView):
    """Архивирование игрового промта."""

    model = ScenarioPrompt
    success_url_name = "adminpanel:scenario_prompt_list"


class AnalysisPromptListView(BackofficeBaseListView):
    """Список аналитических промтов игр."""

    model = AnalysisPrompt
    section_title = "Аналитические промты"
    create_url = "adminpanel:analysis_prompt_create"
    update_url_name = "adminpanel:analysis_prompt_update"
    archive_url_name = "adminpanel:analysis_prompt_archive"


class AnalysisPromptCreateView(BackofficeBaseCreateView):
    """Создание аналитического промта."""

    model = AnalysisPrompt
    form_class = AnalysisPromptForm
    success_url = "/backoffice/analysis-prompts/"


class AnalysisPromptUpdateView(BackofficeBaseUpdateView):
    """Редактирование аналитического промта в админском контуре."""

    model = AnalysisPrompt
    form_class = AnalysisPromptForm
    success_url = "/backoffice/analysis-prompts/"


class AnalysisPromptArchiveView(BackofficeArchiveView):
    """Архивирование аналитического промта."""

    model = AnalysisPrompt
    success_url_name = "adminpanel:analysis_prompt_list"


class SystemPromptListView(BackofficeBaseListView):
    """Список системных промтов с ролевой фильтрацией владельца."""

    model = SystemPrompt
    section_title = "Системные промты"
    create_url = "adminpanel:system_prompt_create"
    update_url_name = "adminpanel:system_prompt_update"
    archive_url_name = "adminpanel:system_prompt_archive"


class SystemPromptCreateView(BackofficeBaseCreateView):
    """Создание системного промта."""

    model = SystemPrompt
    form_class = SystemPromptForm
    success_url = "/backoffice/system-prompts/"


class SystemPromptUpdateView(BackofficeBaseUpdateView):
    """Редактирование системного промта."""

    model = SystemPrompt
    form_class = SystemPromptForm
    success_url = "/backoffice/system-prompts/"


class SystemPromptArchiveView(BackofficeArchiveView):
    """Архивирование системного промта."""

    model = SystemPrompt
    success_url_name = "adminpanel:system_prompt_list"


class MediaListView(BackofficeBaseListView):
    """Список медиа-ресурсов сценариев."""

    model = ScenarioMediaAsset
    section_title = "Медиа-ресурсы"
    create_url = "adminpanel:media_create"
    update_url_name = "adminpanel:media_update"
    archive_url_name = "adminpanel:media_archive"


class MediaCreateView(BackofficeBaseCreateView):
    """Создание медиа-ресурса для сценариев."""

    model = ScenarioMediaAsset
    form_class = ScenarioMediaAssetForm
    success_url = "/backoffice/media/"


class MediaUpdateView(BackofficeBaseUpdateView):
    """Редактирование медиа-ресурса с проверкой владельца."""

    model = ScenarioMediaAsset
    form_class = ScenarioMediaAssetForm
    success_url = "/backoffice/media/"


class MediaArchiveView(BackofficeArchiveView):
    """Архивирование медиа-ресурса сценария."""

    model = ScenarioMediaAsset
    owner_field_name = "uploaded_by"
    success_url_name = "adminpanel:media_list"
