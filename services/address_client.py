"""
HTTP-клиент для микросервиса извлечения адресов (LLM).
"""

from typing import Optional
from urllib.parse import quote

import aiohttp

import config
from logger_config import get_logger

logger = get_logger(__name__)


async def extract_house_id(user_query: str) -> Optional[str]:
    """
    Извлекает house_id из запроса пользователя через LLM address service.

    Returns:
        house_id или None если адрес не найден
    """
    if not config.LLM_URL:
        logger.warning("LLM_URL is not configured, skipping address extraction")
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
                            "Found house_id: %s for query: %s", house_id, user_query
                        )
                        return str(house_id)
                    logger.info(
                        "house_id not found in response for query: %s", user_query
                    )
                    return None

                logger.error("Address service error: HTTP %s", response.status)
                return None

    except Exception as e:
        logger.exception("Error extracting address from query '%s': %s", user_query, e)
        return None
