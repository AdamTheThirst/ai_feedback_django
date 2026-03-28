"""Тесты безопасного парсинга payload в dialog runtime views."""

from django.test import SimpleTestCase
from django.test.client import RequestFactory

from apps.dialogs.views import _extract_request_payload


class DialogPayloadParsingTests(SimpleTestCase):
    """Проверяет устойчивый разбор JSON/form payload без 500-ошибок.

    Контекст использования:
        Фиксирует защиту от сценария, когда поток тела запроса уже был прочитан
        в middleware и последующий доступ к ``request.body`` вызывает
        ``RawPostDataException``.

    Параметры:
        Использует ``RequestFactory`` для создания изолированных POST-запросов.

    Возвращаемое значение:
        Не возвращает значение; выполняет unit-проверки helper-функции.

    Исключения и особые случаи:
        Любое падение на ``RawPostDataException`` считается регрессией.

    Побочные эффекты:
        Побочные эффекты отсутствуют.
    """

    def test_extract_request_payload_fallbacks_to_post_on_raw_body_exception(self) -> None:
        """Проверяет fallback на ``request.POST`` при недоступном ``request.body``.

        Контекст использования:
            Имитирует поведение abandon endpoint-а при form/beacon запросе,
            где тело уже было прочитано до входа в view.

        Параметры:
            Параметры отсутствуют.

        Возвращаемое значение:
            Ничего не возвращает.

        Исключения и особые случаи:
            Исключения не ожидаются; helper должен вернуть корректный словарь.

        Побочные эффекты:
            Создаёт in-memory ``WSGIRequest`` через ``RequestFactory``.
        """

        request = RequestFactory().post("/dialogs/fake/abandon/", data={"reason": "page_leave"})
        _ = request.POST
        request._read_started = True
        if hasattr(request, "_body"):
            delattr(request, "_body")

        payload = _extract_request_payload(request)

        self.assertEqual(payload.get("reason"), "page_leave")
