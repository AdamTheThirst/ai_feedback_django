"""Представления старта диалога, страницы чата и JSON runtime endpoint-ов."""

import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_POST

from apps.content.models import Scenario
from apps.dialogs.models import DialogMessage, DialogSession, DialogSessionStatus
from apps.dialogs.services.runtime import (
    DialogNotActiveError,
    DuplicateSubmissionError,
    choose_active_scenario_prompt,
    compute_seconds_remaining,
    create_dialog_session,
    get_active_dialog_for_user,
    send_user_message,
)


def _dialog_to_payload(dialog: DialogSession) -> dict:
    """Формирует стандартный JSON payload состояния диалога для runtime API.

    Контекст использования:
        Используется endpoint-ами чата для возврата согласованной структуры
        состояния диалоговой сессии клиентскому JavaScript-коду.

    Параметры:
        dialog: Экземпляр диалоговой сессии.

    Возвращаемое значение:
        Словарь состояния диалога в формате API_SPEC.

    Исключения и особые случаи:
        Значение ``seconds_remaining`` для неактивного статуса равно нулю.

    Побочные эффекты:
        Побочные эффекты отсутствуют.
    """

    return {
        "public_id": str(dialog.public_id),
        "status": dialog.status,
        "ended_reason": dialog.ended_reason or None,
        "user_message_count": dialog.user_message_count,
        "assistant_message_count": dialog.assistant_message_count,
        "seconds_remaining": compute_seconds_remaining(dialog),
        "can_send_message": dialog.status == DialogSessionStatus.ACTIVE,
        "can_finish": dialog.status == DialogSessionStatus.ACTIVE,
        "results_url": f"/dialogs/{dialog.public_id}/results/",
    }


def _message_to_payload(message: DialogMessage) -> dict:
    """Преобразует ORM-сообщение в JSON структуру runtime-контракта.

    Контекст использования:
        Нужен для возврата новых сообщений в ответе send-message endpoint-а.

    Параметры:
        message: Сохранённая запись ``DialogMessage``.

    Возвращаемое значение:
        Словарь полей сообщения для JSON-ответа.

    Исключения и особые случаи:
        Особые исключения отсутствуют.

    Побочные эффекты:
        Побочные эффекты отсутствуют.
    """

    return {
        "sequence_no": message.sequence_no,
        "role": message.role,
        "text": message.text,
        "char_count": message.char_count,
        "created_at": message.created_at.isoformat().replace("+00:00", "Z"),
    }


@login_required
@require_GET
def start_scenario_view(request: HttpRequest, scenario_slug: str) -> HttpResponse:
    """Запускает сценарий либо возвращает пользователя в активный диалог.

    Контекст использования:
        Реализует маршрут ``/scenarios/<scenario_slug>/play/`` для старта runtime.

    Параметры:
        request: HTTP-запрос авторизованного пользователя.
        scenario_slug: Slug сценария из URL.

    Возвращаемое значение:
        Redirect на страницу диалога.

    Исключения и особые случаи:
        При неоднозначном slug или отсутствии активного промта показывает ошибку
        и возвращает на страницу списка игр.

    Побочные эффекты:
        Может создать новый ``DialogSession`` и стартовое сообщение ассистента.
    """

    active_dialog = get_active_dialog_for_user(request.user.id)
    if active_dialog is not None:
        messages.info(request, "У вас уже есть активный диалог. Возвращаем в него.")
        return redirect("dialogs:dialog_detail", dialog_public_id=active_dialog.public_id)

    scenario_qs = Scenario.objects.filter(
        slug=scenario_slug,
        is_published=True,
        is_archived=False,
        game__is_archived=False,
    ).select_related("game")

    if scenario_qs.count() != 1:
        messages.error(request, "Сценарий не найден или неоднозначен.")
        return redirect("content:game_list")

    scenario = scenario_qs.first()
    prompt = choose_active_scenario_prompt(scenario=scenario)
    if prompt is None:
        messages.error(request, "Для сценария не найден активный игровой промт.")
        return redirect("content:game_detail", game_slug=scenario.game.slug)

    dialog = create_dialog_session(user_id=request.user.id, scenario=scenario, scenario_prompt=prompt)
    return redirect("dialogs:dialog_detail", dialog_public_id=dialog.public_id)


@login_required
@require_GET
def dialog_detail_view(request: HttpRequest, dialog_public_id: str) -> HttpResponse:
    """Отображает страницу чата выбранного диалога с историей сообщений.

    Контекст использования:
        Реализует HTML runtime-экран ``/dialogs/<dialog_public_id>/``.

    Параметры:
        request: HTTP-запрос пользователя.
        dialog_public_id: Публичный ID диалоговой сессии.

    Возвращаемое значение:
        HTML-страница чата.

    Исключения и особые случаи:
        Доступ разрешён только владельцу диалога.

    Побочные эффекты:
        Побочные эффекты отсутствуют.
    """

    dialog = get_object_or_404(
        DialogSession.objects.select_related("game", "scenario"),
        public_id=dialog_public_id,
        user=request.user,
    )
    messages_qs = dialog.messages.order_by("sequence_no")

    return render(
        request,
        "dialogs/dialog_detail.html",
        {
            "dialog": dialog,
            "messages": messages_qs,
            "seconds_remaining": compute_seconds_remaining(dialog),
            "can_send_message": dialog.status == DialogSessionStatus.ACTIVE,
            "send_url": f"/dialogs/{dialog.public_id}/send-message/",
        },
    )


@login_required
@require_POST
def send_message_view(request: HttpRequest, dialog_public_id: str) -> JsonResponse:
    """Принимает пользовательскую реплику и возвращает JSON с двумя сообщениями.

    Контекст использования:
        Реализует async endpoint ``/dialogs/<dialog_public_id>/send-message/``.

    Параметры:
        request: HTTP-запрос с JSON телом ``{"text": "..."}``.
        dialog_public_id: Публичный идентификатор текущего диалога.

    Возвращаемое значение:
        JSON-ответ успеха или контролируемой ошибки.

    Исключения и особые случаи:
        Возвращает коды ``empty_message``, ``message_too_long``,
        ``dialog_not_active`` и ``duplicate_submission_blocked``.

    Побочные эффекты:
        Создаёт сообщения в БД и обновляет счётчики диалога.
    """

    dialog = get_object_or_404(DialogSession, public_id=dialog_public_id, user=request.user)

    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return JsonResponse(
            {"ok": False, "code": "invalid_json", "message": "Некорректный JSON.", "data": {}},
            status=400,
        )

    text = (payload.get("text") or "").strip()
    if not text:
        return JsonResponse(
            {"ok": False, "code": "empty_message", "message": "Сообщение пустое.", "data": {}},
            status=400,
        )

    if len(text) > dialog.effective_user_message_max_chars:
        return JsonResponse(
            {
                "ok": False,
                "code": "message_too_long",
                "message": "Сообщение превышает лимит длины.",
                "data": {"max_chars": dialog.effective_user_message_max_chars},
            },
            status=400,
        )

    try:
        result = send_user_message(dialog=dialog, text=text)
    except DuplicateSubmissionError:
        return JsonResponse(
            {
                "ok": False,
                "code": "duplicate_submission_blocked",
                "message": "Повторная отправка заблокирована.",
                "data": {},
            },
            status=409,
        )
    except DialogNotActiveError:
        return JsonResponse(
            {
                "ok": False,
                "code": "dialog_not_active",
                "message": "Диалог уже не активен.",
                "data": {"dialog": _dialog_to_payload(dialog)},
            },
            status=409,
        )

    return JsonResponse(
        {
            "ok": True,
            "code": "ok",
            "message": "",
            "data": {
                "dialog": _dialog_to_payload(result.dialog),
                "user_message": _message_to_payload(result.user_message),
                "assistant_message": _message_to_payload(result.assistant_message),
            },
        }
    )
