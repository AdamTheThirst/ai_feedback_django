"""Представления старта, отправки, завершения и финального состояния диалога."""

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
    DuplicateFinishError,
    DuplicateSubmissionError,
    abandon_dialog,
    choose_active_scenario_prompt,
    compute_seconds_remaining,
    create_dialog_session,
    finish_dialog,
    get_active_dialog_for_user,
    send_user_message,
)


def _dialog_to_payload(dialog: DialogSession) -> dict:
    """Преобразует модель диалога в JSON payload состояния runtime."""

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
    """Преобразует ORM-сообщение в JSON формат runtime API."""

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
    """Запускает сценарий либо возвращает пользователя в уже активный диалог."""

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
    """Отображает страницу чата и текущего runtime-состояния диалога."""

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
            "finish_url": f"/dialogs/{dialog.public_id}/finish/",
            "abandon_url": f"/dialogs/{dialog.public_id}/abandon/",
            "results_url": f"/dialogs/{dialog.public_id}/results/",
        },
    )


@login_required
@require_GET
def dialog_results_view(request: HttpRequest, dialog_public_id: str) -> HttpResponse:
    """Показывает финальное состояние диалога до этапа полноценной аналитики."""

    dialog = get_object_or_404(DialogSession, public_id=dialog_public_id, user=request.user)
    return render(request, "dialogs/dialog_results.html", {"dialog": dialog})


@login_required
@require_POST
def send_message_view(request: HttpRequest, dialog_public_id: str) -> JsonResponse:
    """Сохраняет пользовательскую реплику и возвращает JSON с ответом ассистента."""

    dialog = get_object_or_404(DialogSession, public_id=dialog_public_id, user=request.user)

    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"ok": False, "code": "invalid_json", "message": "Некорректный JSON.", "data": {}}, status=400)

    text = (payload.get("text") or "").strip()
    if not text:
        return JsonResponse({"ok": False, "code": "empty_message", "message": "Сообщение пустое.", "data": {}}, status=400)

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
        return JsonResponse({"ok": False, "code": "duplicate_submission_blocked", "message": "Повторная отправка заблокирована.", "data": {}}, status=409)
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


@login_required
@require_POST
def finish_dialog_view(request: HttpRequest, dialog_public_id: str) -> JsonResponse:
    """Завершает активный диалог вручную или по таймеру с защитой от дублей."""

    dialog = get_object_or_404(DialogSession, public_id=dialog_public_id, user=request.user)

    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        payload = {}

    reason = payload.get("reason") or "manual_feedback"
    try:
        updated_dialog = finish_dialog(dialog=dialog, reason=reason)
    except ValueError:
        return JsonResponse({"ok": False, "code": "invalid_reason", "message": "Недопустимая причина завершения.", "data": {}}, status=400)
    except DuplicateFinishError:
        return JsonResponse({"ok": False, "code": "duplicate_finish_blocked", "message": "Повторное завершение заблокировано.", "data": {}}, status=409)
    except DialogNotActiveError:
        return JsonResponse({"ok": False, "code": "dialog_not_active", "message": "Диалог уже завершён.", "data": {"dialog": _dialog_to_payload(dialog)}}, status=409)

    return JsonResponse(
        {
            "ok": True,
            "code": "finished",
            "message": "",
            "data": {
                "dialog": _dialog_to_payload(updated_dialog),
                "redirect_url": f"/dialogs/{updated_dialog.public_id}/results/",
            },
        }
    )


@login_required
@require_POST
def abandon_dialog_view(request: HttpRequest, dialog_public_id: str) -> JsonResponse:
    """Прерывает диалог при уходе со страницы и защищает от дублей запроса."""

    dialog = get_object_or_404(DialogSession, public_id=dialog_public_id, user=request.user)

    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        payload = {}

    reason = payload.get("reason") or request.POST.get("reason") or "page_leave"
    try:
        updated_dialog = abandon_dialog(dialog=dialog, reason=reason)
    except ValueError:
        return JsonResponse({"ok": False, "code": "invalid_reason", "message": "Недопустимая причина прерывания.", "data": {}}, status=400)
    except DuplicateFinishError:
        return JsonResponse({"ok": False, "code": "duplicate_abandon_blocked", "message": "Повторный abandon заблокирован.", "data": {}}, status=409)
    except DialogNotActiveError:
        return JsonResponse({"ok": False, "code": "dialog_not_active", "message": "Диалог уже завершён.", "data": {"dialog": _dialog_to_payload(dialog)}}, status=409)

    return JsonResponse(
        {
            "ok": True,
            "code": "abandoned",
            "message": "",
            "data": {
                "dialog": _dialog_to_payload(updated_dialog),
                "redirect_url": f"/dialogs/{updated_dialog.public_id}/results/",
            },
        }
    )
