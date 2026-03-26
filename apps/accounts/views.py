"""Представления регистрации, входа, выхода и сброса пароля."""

from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.views import (
    PasswordResetCompleteView,
    PasswordResetConfirmView,
    PasswordResetDoneView,
    PasswordResetView,
)
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.views import View

from apps.accounts.forms import EmailAuthenticationForm, RegistrationForm
from apps.accounts.services.auth_rate_limit import (
    MAX_FAILED_ATTEMPTS,
    is_blocked,
    register_failed_attempt,
    reset_failed_attempts,
)
from apps.auditlog.models import AuditLogEntry, AuditLogLevel


class RegisterView(View):
    """Отображает форму регистрации и создаёт новую пользовательскую учётку.

    Контекст использования:
        Используется как публичная точка входа ``/auth/register/`` в первой версии.

    Параметры:
        Работает со стандартными HTTP GET/POST запросами.

    Возвращаемое значение:
        Возвращает HTML-страницу формы или redirect на главную после успеха.

    Исключения и особые случаи:
        Ошибки валидации остаются на форме без создания пользователя.

    Побочные эффекты:
        При успешной регистрации создаёт пользователя и открывает сессию.
    """

    template_name = "accounts/register.html"

    def get(self, request: HttpRequest) -> HttpResponse:
        """Рендерит пустую форму регистрации.

        Контекст использования:
            Вызывается при первом открытии страницы регистрации.

        Параметры:
            request: Входящий HTTP-запрос.

        Возвращаемое значение:
            HTML-ответ с формой регистрации.

        Исключения и особые случаи:
            Исключения не ожидаются при штатном выполнении.

        Побочные эффекты:
            Побочные эффекты отсутствуют.
        """

        form = RegistrationForm()
        return render(request, self.template_name, {"form": form})

    def post(self, request: HttpRequest) -> HttpResponse:
        """Валидирует форму регистрации, создаёт пользователя и логинит его.

        Контекст использования:
            Вызывается после отправки формы регистрации из браузера.

        Параметры:
            request: HTTP-запрос с данными формы регистрации.

        Возвращаемое значение:
            Redirect на главную страницу при успехе или HTML с ошибками.

        Исключения и особые случаи:
            При невалидных данных создаётся ответ с той же формой.

        Побочные эффекты:
            Создаёт пользователя в БД и открывает пользовательскую сессию.
        """

        form = RegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, "Регистрация прошла успешно.")
            return redirect("core:home")
        return render(request, self.template_name, {"form": form})


class LoginView(View):
    """Обрабатывает вход пользователя через email и пароль.

    Контекст использования:
        Используется как публичная точка входа ``/auth/login/``.

    Параметры:
        Принимает стандартные HTTP GET/POST запросы.

    Возвращаемое значение:
        Возвращает HTML-страницу формы или redirect на главную.

    Исключения и особые случаи:
        При превышении лимита входа выводит общее сообщение об ожидании.

    Побочные эффекты:
        При успехе открывает сессию; при ошибках увеличивает счётчик попыток.
    """

    template_name = "accounts/login.html"

    def get(self, request: HttpRequest) -> HttpResponse:
        """Рендерит форму входа для пользователя.

        Контекст использования:
            Вызывается при открытии страницы входа.

        Параметры:
            request: Входящий HTTP-запрос.

        Возвращаемое значение:
            HTML-ответ со страницей входа.

        Исключения и особые случаи:
            Если пользователь уже аутентифицирован, выполняется redirect на главную.

        Побочные эффекты:
            Побочные эффекты отсутствуют.
        """

        if request.user.is_authenticated:
            return redirect("core:home")
        form = EmailAuthenticationForm(request=request)
        return render(request, self.template_name, {"form": form})

    def post(self, request: HttpRequest) -> HttpResponse:
        """Проверяет данные входа с учётом rate-limit и выполняет логин.

        Контекст использования:
            Вызывается при отправке формы входа пользователем.

        Параметры:
            request: HTTP-запрос с email и паролем.

        Возвращаемое значение:
            Redirect на главную при успехе или HTML с ошибкой при неуспехе.

        Исключения и особые случаи:
            При превышении лимита попыток вход блокируется на короткое окно.

        Побочные эффекты:
            Создаёт аудит-лог и обновляет счётчики rate-limit в кэше.
        """

        ip_address = request.META.get("REMOTE_ADDR", "")
        email = (request.POST.get("email") or "").strip().lower()

        if is_blocked(email=email, ip_address=ip_address):
            AuditLogEntry.objects.create(
                level=AuditLogLevel.WARNING,
                event_type="auth.login_rate_limited",
                message="Превышен допустимый темп попыток входа.",
                context_json={"email": email, "ip": ip_address},
            )
            messages.error(
                request,
                "Слишком много попыток входа. Повторите позже.",
            )
            form = EmailAuthenticationForm(request=request, data=request.POST)
            return render(request, self.template_name, {"form": form})

        form = EmailAuthenticationForm(request=request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            if user is not None:
                login(request, user)
                reset_failed_attempts(email=email, ip_address=ip_address)
                return redirect("core:home")

        attempts = register_failed_attempt(email=email, ip_address=ip_address)
        if attempts >= MAX_FAILED_ATTEMPTS:
            AuditLogEntry.objects.create(
                level=AuditLogLevel.WARNING,
                event_type="auth.login_rate_limited",
                message="Превышен допустимый темп попыток входа.",
                context_json={"email": email, "ip": ip_address, "attempts": attempts},
            )
        return render(request, self.template_name, {"form": form})


class LogoutView(View):
    """Завершает пользовательскую сессию и перенаправляет на страницу входа.

    Контекст использования:
        Используется маршрутом ``/auth/logout/`` и ожидает POST-запрос.

    Параметры:
        Принимает HTTP-запрос текущего пользователя.

    Возвращаемое значение:
        Redirect на страницу входа.

    Исключения и особые случаи:
        Если пользователь не авторизован, поведение остаётся безопасным.

    Побочные эффекты:
        Завершает активную сессию пользователя.
    """

    def post(self, request: HttpRequest) -> HttpResponse:
        """Выполняет logout текущего пользователя.

        Контекст использования:
            Вызывается при нажатии кнопки «Выйти» на защищённых страницах.

        Параметры:
            request: HTTP-запрос пользователя.

        Возвращаемое значение:
            Redirect на страницу входа.

        Исключения и особые случаи:
            Специальные исключения не предусмотрены.

        Побочные эффекты:
            Сбрасывает данные аутентификационной сессии.
        """

        logout(request)
        return redirect("accounts:login")


class ProjectPasswordResetView(PasswordResetView):
    """Адаптированный экран запроса сброса пароля для проекта.

    Контекст использования:
        Используется публичным маршрутом ``/auth/password-reset/``.

    Параметры:
        Применяет стандартный flow Django с проектными шаблонами.

    Возвращаемое значение:
        HTML-страница запроса или redirect на страницу подтверждения отправки.

    Исключения и особые случаи:
        Поведение отправки email зависит от текущего EMAIL backend.

    Побочные эффекты:
        При существующем email инициирует отправку письма для сброса пароля.
    """

    template_name = "registration/password_reset_form.html"
    email_template_name = "registration/password_reset_email.txt"
    subject_template_name = "registration/password_reset_subject.txt"
    success_url = reverse_lazy("accounts:password_reset_done")


class ProjectPasswordResetDoneView(PasswordResetDoneView):
    """Экран подтверждения отправки письма для сброса пароля.

    Контекст использования:
        Завершает первый шаг password-reset flow после отправки формы.

    Параметры:
        Использует стандартный GET-запрос без дополнительных параметров.

    Возвращаемое значение:
        HTML-страница с уведомлением о проверке почты.

    Исключения и особые случаи:
        Исключения не ожидаются при штатной конфигурации.

    Побочные эффекты:
        Побочные эффекты отсутствуют.
    """

    template_name = "registration/password_reset_done.html"


class ProjectPasswordResetConfirmView(PasswordResetConfirmView):
    """Экран ввода нового пароля по ссылке из письма восстановления.

    Контекст использования:
        Используется маршрутом подтверждения токена сброса пароля.

    Параметры:
        Работает со стандартными параметрами ``uidb64`` и ``token`` в URL.

    Возвращаемое значение:
        HTML-форма установки нового пароля или redirect на финальный экран.

    Исключения и особые случаи:
        При невалидной или просроченной ссылке показывает сообщение Django.

    Побочные эффекты:
        При валидной отправке обновляет пароль пользователя.
    """

    template_name = "registration/password_reset_confirm.html"
    success_url = reverse_lazy("accounts:password_reset_complete")


class ProjectPasswordResetCompleteView(PasswordResetCompleteView):
    """Финальный экран успешного завершения восстановления пароля.

    Контекст использования:
        Показывается после успешной установки нового пароля пользователем.

    Параметры:
        Дополнительные параметры не требуются.

    Возвращаемое значение:
        HTML-страница с предложением перейти ко входу.

    Исключения и особые случаи:
        Исключения не ожидаются.

    Побочные эффекты:
        Побочные эффекты отсутствуют.
    """

    template_name = "registration/password_reset_complete.html"
