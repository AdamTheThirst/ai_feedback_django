"""Маршруты чатового runtime: старт сценария, страница диалога и send-message."""

from django.urls import path

from apps.dialogs.views import dialog_detail_view, send_message_view, start_scenario_view

app_name = "dialogs"

urlpatterns = [
    path("scenarios/<slug:scenario_slug>/play/", start_scenario_view, name="start_scenario"),
    path("dialogs/<uuid:dialog_public_id>/", dialog_detail_view, name="dialog_detail"),
    path(
        "dialogs/<uuid:dialog_public_id>/send-message/",
        send_message_view,
        name="send_message",
    ),
]
