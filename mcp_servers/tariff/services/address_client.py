"""HTTP-клиент сервиса извлечения адресов (LLM)."""

from typing import Optional
from urllib.parse import quote

import aiohttp

from mcp_servers.tariff import config
from shared.logging import get_logger

logger = get_logger(__name__)


async def extract_house_id(user_query: str) -> Optional[str]:
    if not config.LLM_URL:
        logger.warning("LLM_URL не настроен, пропускаем извлечение адреса")
        return None

    try:
        encoded_query = quote(user_query)
        url = f"{config.LLM_URL.rstrip('/')}/api/v1/adress?query={encoded_query}"

        async with aiohttp.ClientSession() as session:
            async with session.get(
                url, headers={"accept": "application/json"}
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    house_id = data.get("houseid")
                    if house_id:
                        logger.info(
                            "Найден house_id: %s для запроса: %s", house_id, user_query
                        )
                        return str(house_id)
                    logger.info(
                        "house_id не найден в ответе для запроса: %s", user_query
                    )
                    return None

                logger.error("Ошибка сервиса адресов: HTTP %s", response.status)
                return None

    except Exception as e:
        logger.exception(
            "Ошибка извлечения адреса из запроса '%s': %s", user_query, e
        )
        return None
