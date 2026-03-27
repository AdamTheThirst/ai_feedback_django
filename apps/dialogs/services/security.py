"""Сервис security-ограничений runtime-эндпоинтов диалога."""

from django.core.cache import cache

RATE_LIMIT_MAX_REQUESTS = 20
RATE_LIMIT_WINDOW_SECONDS = 10


def _build_send_rate_limit_key(user_id: int, dialog_public_id: str) -> str:
    """Строит ключ счётчика rate-limit для отправки сообщений диалога.

    Контекст использования:
        Используется для защиты endpoint-а отправки сообщения от аномально
        частых запросов в коротком интервале времени.

    Параметры:
        user_id: Идентификатор текущего пользователя.
        dialog_public_id: Публичный идентификатор диалоговой сессии.

    Возвращаемое значение:
        Строка ключа для кэша Django.

    Исключения и особые случаи:
        Особые исключения отсутствуют.

    Побочные эффекты:
        Побочные эффекты отсутствуют.
    """

    return f"dialogs:send-rate-limit:{user_id}:{dialog_public_id}"


def consume_send_message_rate_limit(user_id: int, dialog_public_id: str) -> bool:
    """Инкрементирует счётчик отправки и проверяет лимит частоты запросов.

    Контекст использования:
        Вызывается перед обработкой payload в ``send_message_view`` для
        предотвращения спама и снижения риска DoS на runtime-эндпоинт.

    Параметры:
        user_id: Идентификатор пользователя, отправляющего сообщение.
        dialog_public_id: Публичный UUID диалога.

    Возвращаемое значение:
        ``True``, если запрос укладывается в лимит; иначе ``False``.

    Исключения и особые случаи:
        При недоступности backend кэша Django может выбросить исключение выше по стеку.

    Побочные эффекты:
        Создаёт/обновляет счётчик в кэше с TTL окна rate-limit.
    """

    key = _build_send_rate_limit_key(user_id=user_id, dialog_public_id=dialog_public_id)
    if cache.add(key, 1, RATE_LIMIT_WINDOW_SECONDS):
        return True

    try:
        current_value = cache.incr(key)
    except ValueError:
        cache.set(key, 1, RATE_LIMIT_WINDOW_SECONDS)
        return True
    return int(current_value) <= RATE_LIMIT_MAX_REQUESTS
