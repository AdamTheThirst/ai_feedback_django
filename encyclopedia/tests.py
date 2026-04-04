"""Тесты раздела энциклопедии: модель, маршруты и права доступа."""

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import Client, TestCase
from django.urls import reverse

from encyclopedia.models import EncyclopediaArticle


class EncyclopediaArticleModelTests(TestCase):
    """Проверяет поведение модели статьи энциклопедии."""

    def test_slug_is_generated_and_stable(self) -> None:
        """Проверяет автогенерацию slug и его стабильность при редактировании.

        Тест подтверждает, что slug создаётся один раз на основе заголовка
        и не меняется автоматически при последующих изменениях title.
        """
        article = EncyclopediaArticle.objects.create(
            title="Я-сообщения в переговорах",
            body="Полезный текст статьи" * 20,
            summary="Краткое описание статьи, которое укладывается в лимит длины и является осмысленным.",
            is_published=True,
        )
        initial_slug = article.slug
        article.title = "Новый заголовок"
        article.save()
        article.refresh_from_db()
        self.assertEqual(article.slug, initial_slug)

    def test_title_validation_rejects_html(self) -> None:
        """Проверяет запрет HTML-тегов в заголовке статьи.

        Тест нужен для серверной валидации поля `title` согласно ТЗ.
        """
        article = EncyclopediaArticle(
            title="<b>Запрещено</b>",
            body="Текст" * 100,
            summary="Краткое описание статьи, которое укладывается в лимит длины и является осмысленным.",
            is_published=True,
        )
        with self.assertRaises(ValidationError):
            article.full_clean()


class EncyclopediaViewsTests(TestCase):
    """Проверяет пользовательские страницы списка и карточки статьи."""

    def setUp(self) -> None:
        """Создаёт тестового пользователя и клиент для авторизованных запросов."""
        user_model = get_user_model()
        self.user = user_model.objects.create_user(username="user", password="password-123")
        self.client = Client()

    def _create_article(self, title: str, is_published: bool = True) -> EncyclopediaArticle:
        """Создаёт тестовую статью с валидными значениями полей.

        :param title: Заголовок создаваемой статьи.
        :param is_published: Признак публикации.
        :return: Экземпляр созданной статьи.
        """
        return EncyclopediaArticle.objects.create(
            title=title,
            body="Текст статьи " * 40,
            summary="Краткое описание статьи, которое укладывается в лимит длины и является осмысленным.",
            is_published=is_published,
        )

    def test_list_requires_authentication(self) -> None:
        """Проверяет, что список статей доступен только авторизованным."""
        response = self.client.get(reverse("encyclopedia:list"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response.url)

    def test_only_published_articles_are_visible(self) -> None:
        """Проверяет фильтрацию списка только по опубликованным статьям."""
        self.client.force_login(self.user)
        published = self._create_article("1. Опубликовано", is_published=True)
        self._create_article("2. Черновик", is_published=False)

        response = self.client.get(reverse("encyclopedia:list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, published.title)
        self.assertNotContains(response, "2. Черновик")

    def test_sorting_digits_then_cyrillic_then_latin(self) -> None:
        """Проверяет порядок сортировки заголовков в списке энциклопедии."""
        self.client.force_login(self.user)
        a1 = self._create_article("Бета статья")
        a2 = self._create_article("Alpha article")
        a3 = self._create_article("1 Первая")

        response = self.client.get(reverse("encyclopedia:list"))
        content = response.content.decode("utf-8")

        self.assertLess(content.find(a3.title), content.find(a1.title))
        self.assertLess(content.find(a1.title), content.find(a2.title))

    def test_pagination_has_10_items_per_page(self) -> None:
        """Проверяет постраничный вывод по 10 опубликованных статей."""
        self.client.force_login(self.user)
        for index in range(12):
            self._create_article(f"{index} Статья")

        response = self.client.get(reverse("encyclopedia:list"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["page_obj"].object_list), 10)

    def test_detail_hidden_for_unpublished_article(self) -> None:
        """Проверяет недоступность неопубликованной статьи в пользовательском UI."""
        self.client.force_login(self.user)
        article = self._create_article("Скрытая статья", is_published=False)

        response = self.client.get(reverse("encyclopedia:detail", kwargs={"slug": article.slug}))
        self.assertEqual(response.status_code, 404)
