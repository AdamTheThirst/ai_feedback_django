"""URL-маршруты пользовательского раздела энциклопедии."""

from django.urls import path

from encyclopedia import views

app_name = "encyclopedia"

urlpatterns = [
    path("", views.article_list, name="list"),
    path("<slug:slug>/", views.article_detail, name="detail"),
]
