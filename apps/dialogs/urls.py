"""Маршруты runtime-чата: старт, send-message, finish, abandon и результаты."""

from django.urls import path

from apps.dialogs.views import (
    abandon_dialog_view,
    dialog_detail_view,
    dialog_results_view,
    finish_dialog_view,
    send_message_view,
    start_scenario_view,
)

app_name = "dialogs"

urlpatterns = [
    path("scenarios/<slug:scenario_slug>/play/", start_scenario_view, name="start_scenario"),
    path("dialogs/<uuid:dialog_public_id>/", dialog_detail_view, name="dialog_detail"),
    path("dialogs/<uuid:dialog_public_id>/results/", dialog_results_view, name="dialog_results"),
    path("dialogs/<uuid:dialog_public_id>/send-message/", send_message_view, name="send_message"),
    path("dialogs/<uuid:dialog_public_id>/finish/", finish_dialog_view, name="finish_dialog"),
    path("dialogs/<uuid:dialog_public_id>/abandon/", abandon_dialog_view, name="abandon_dialog"),
]
