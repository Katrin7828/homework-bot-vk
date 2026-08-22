import logging
import sys
import os
import random
import time
from http import HTTPStatus

import requests
import vk_api
from dotenv import load_dotenv

from exceptions import APIResponseError


load_dotenv()

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

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


def get_api_answer(timestamp):
    """Делает запрос к единственному эндпоинту API-сервиса."""
    logger.info(f'Выполняется запрос к API {ENDPOINT}'
                f'с параметром from_date={timestamp}')
    try:
        response = requests.get(ENDPOINT, headers=HEADERS,
                                params={'from_date': timestamp})
        data = response.json()
    except requests.RequestException as error:
        raise ConnectionError(
            f'Сбой при запросе к API {ENDPOINT} с параметрами'
            f'from_date={timestamp}. Ошибка: {error}')
    if response.status_code != HTTPStatus.OK:
        raise APIResponseError(
            f'API {ENDPOINT} вернул статус {response.status_code}'
            f'при запросе с from_date={timestamp}.'
            f'({response.reason}) при запросе с from_date={timestamp}.')
    logger.info(f'Запрос к API {ENDPOINT} выполнен успешно.'
                f'Получено {len(data.get("homeworks", []))} работ')
    return data


def check_response(response):
    """Проверяет ответ API на соответствие документации из урока."""
    logger.info('Начинаем проверку ответа API')
    if not isinstance(response, dict):
        raise TypeError(
            'Ожидался dict, а получен {type(homeworks).__name__}')
    if 'homeworks' not in response:
        raise KeyError('В ответе API отсутствует ключ "homeworks."')
    homeworks = response['homeworks']
    if not isinstance(homeworks, list):
        raise TypeError('Значение по ключу "homeworks" должно быть списком,'
                        f'а получен {type(homeworks).__name__}')
    logger.debug('Ответ API успешно проверен.'
                 f'Получено {len(homeworks)} работ.')
    logger.info('Ответ API успешно проверен.'
                f'Получено {len(homeworks)} работ.')
    return homeworks


def parse_status(homework):
    """Извлекает из информации о домашней работе статус этой работы."""
    logger.info('Начинаем получать статус домашней работы')
    if 'homework_name' not in homework:
        raise KeyError('Отсутствует ключ "homework_name".')
    homework_name = homework.get('homework_name')
    if 'status' not in homework:
        raise KeyError('Отсутствует ключ "status".')
    status = homework.get('status')
    if status not in HOMEWORK_VERDICTS:
        raise APIResponseError(f'Неизвестный статус работы: {status}')
    verdict = HOMEWORK_VERDICTS[status]
    logger.info(f'Получен статус домашней работы:{status}')
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        logger.critical('Отсутствуют обязательные переменные окружения.')
        sys.exit()

    vk_session = vk_api.VkApi(token=VK_TOKEN)
    vk = vk_session.get_api()
    timestamp = int(time.time())

    last_error_message = None

    while True:
        try:
            response = get_api_answer(timestamp)
            homeworks = check_response(response)
            if homeworks:
                homework = homeworks[0]
                message = parse_status(homework)
                send_message(vk, message)
            timestamp = response.get('current_date', int(time.time()))
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logger.error(message)
            if message != last_error_message:
                send_message(vk, message)
                last_error_message = message
            else:
                logger.debug('Сообщение об ошибке уже было отправлено ранее')

        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
    )
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)

    main()
