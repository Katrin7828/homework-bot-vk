class APIResponseError(Exception):
    """Ошибка при работе с API сервиса."""

    pass


class SendMessageError(Exception):
    """Ошибка при отправке сообщения в VK."""

    pass
