import logging
import sys
import os
import random
import time
from http import HTTPStatus

import requests
import vk_api
from dotenv import load_dotenv

from exceptions import APIResponseError, SendMessageError


load_dotenv()

logger = logging.getLogger(__name__)

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
VK_TOKEN = os.getenv('VK_TOKEN')
VK_USER_ID = os.getenv('VK_USER_ID')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.',
}


def check_tokens():
    """Проверяет доступность переменных окружения.

    Которые необходимы для работы программы.
    Если отсутствует хотя бы одна переменная окружения —
    продолжать работу бота нет смысла.
    """
    tokens = [PRACTICUM_TOKEN, VK_TOKEN, VK_USER_ID]
    if not all(tokens):
        logger.critical('Отсутствуют обязательные переменные окружения.')
        return False
    logger.debug('Все переменные окружения доступны.')
    return True


def send_message(vk, message):
    """Отправляет сообщение в VK-чат."""
    try:
        logging.debug('Начинаем отправку сообщения в VK.')
        vk.messages.send(
            user_id=VK_USER_ID,
            message=message,
            random_id=random.randint(0, 100000),
        )
        logger.debug('Сообщение успешно отправлено в VK.')
    except Exception as error:
        logger.error('Сбой при отправке сообщения в VK', error)
        raise SendMessageError('Не удалось отправить сообщение в VK.')


def get_api_answer(timestamp):
    """Делает запрос к единственному эндпоинту API-сервиса."""
    try:
        response = requests.get(ENDPOINT, headers=HEADERS,
                                params={'from_date': timestamp})
    except requests.RequestException:
        logger.error('Сбой при запросе к эндпоинту.')
        raise APIResponseError('Сбой при запросе к API.')
    if response.status_code != HTTPStatus.OK:
        logger.error('Ошибка от API.')
        raise APIResponseError('Ошибка ответа от API Яндекс Практикума.')
    try:
        return response.json()
    except ValueError:
        logger.error('Ошибка парсинга JSON.')
        raise APIResponseError('Не удалось обработать ответ API.')


def check_response(response):
    """Проверяет ответ API на соответствие документации из урока."""
    if response is None:
        logger.error('Ответ API равен None.')
        raise TypeError
    if not isinstance(response, dict):
        logger.error('Ответ API не является словарём.')
        raise TypeError
    if 'homeworks' not in response:
        logger.error('В ответе API отсутствует ключ "homeworks."')
        raise APIResponseError('В ответе API отсутствует ключ "homeworks."')
    homeworks = response['homeworks']
    if not isinstance(homeworks, list):
        logger.error('Значение по ключу "homeworks" не является списком.')
        raise TypeError
    logger.debug('Ответ API успешно проверен.'
                 f'Получено {len(homeworks)} работ.')
    return homeworks


def parse_status(homework):
    """Извлекает из информации о домашней работе статус этой работы."""
    if 'homework_name' not in homework:
        logger.error('В домашней работе отсутствует ключ "homework_name".')
        raise APIResponseError('Отсутствует ключ "homework_name".')
    homework_name = homework.get('homework_name')
    status = homework.get('status')
    if 'status' not in homework:
        logger.error(f'Неизвестный статус домашней работы: {status}.')
        raise APIResponseError('Неизвестный статус работы.')
    if status not in HOMEWORK_VERDICTS:
        logger.error(f'Неожиданный статус домашней работы: "{status}"'
                     f'для работы "{homework_name}".')
        raise APIResponseError(f'Неизвестный статус работы: {status}')
    verdict = HOMEWORK_VERDICTS[status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        logger.critical('Отсутствуют обязательные переменные окружения.')
        sys.exit()

    vk_session = vk_api.VkApi(token=VK_TOKEN)
    vk = vk_session.get_api()
    timestamp = int(time.time())

    while True:
        try:
            response = get_api_answer(timestamp)
            homeworks = check_response(response)
            if homeworks:
                homework = homeworks[0]
                message = parse_status(homework)
                send_message(vk, message)
            timestamp = response.get('current_date')
        except APIResponseError:
            logger.debug('В ответе API нет новых статусов.')

        except TypeError as error:
            message = f'Ошибка типа данных в ответе API: {error}'
            logger.error(message)

        except APIResponseError as error:
            message = f'Сбой в работе программы: {error}'
            logger.error(message)

        except SendMessageError as error:
            message = f'Сбой при отправке сообщения: {error}'
            logger.error(message)

        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            send_message(vk, message)

        time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    logger.setLevel(logging.DEBUG)
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
    )
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)

    main()
