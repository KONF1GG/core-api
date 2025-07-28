"""
CRUD операции для работы с внешними сервисами Frida.

Содержит функции для аутентификации через 1С систему.
"""

from typing import Dict
from aiohttp import ClientSession

from logger_config import get_logger
from .schemas import Employee1C

logger = get_logger(__name__)


async def auth_1c(telegramid: int) -> Employee1C | Dict[str, str]:
    """
    Проверяет сотрудника по telegram ID через 1С систему.

    Args:
        telegramid: ID пользователя в Telegram

    Returns:
        Employee1C | Dict[str, str]: Данные сотрудника или сообщение об ошибке
    """
    url = f"http://server1c.freedom1.ru/UNF_CRM_WS/hs/Grafana/anydata?query=emploeyy&telegramId={telegramid}"

    logger.debug("Checking employee in 1C for telegram ID: %s", telegramid)

    try:
        async with ClientSession() as session:
            async with session.get(url) as res:
                if res.status != 200:
                    logger.warning(
                        "1C service returned status %s for user %s",
                        res.status,
                        telegramid,
                    )
                    return {"error": "Ошибка соединения с 1С"}

                data = await res.json(content_type=None)

                if not data:
                    logger.info("User %s not found in 1C", telegramid)
                    return {"error": "Доступ запрещён"}

                fio = data.get("fio")
                job_title = data.get("jobTitle")

                if fio and job_title:
                    logger.info(
                        "User %s authenticated successfully in 1C: %s", telegramid, fio
                    )
                    return Employee1C(fio=fio, jobTitle=job_title)

                logger.warning("Incomplete data from 1C for user %s", telegramid)
                return {"error": "Неизвестный ответ от 1С"}

    except Exception as e:
        logger.error("Error during 1C authentication for user %s: %s", telegramid, e)
        return {"error": "Ошибка соединения с 1С"}
