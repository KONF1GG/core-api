"""
Зависимости FastAPI для подключения к внешним сервисам.

Содержит генераторы подключений к Redis и другим сервисам,
используемые в роутах через dependency injection.
"""

from typing import Annotated, Any, AsyncGenerator
from redis.asyncio import Redis, from_url
from fastapi import Depends

import config
from logger_config import get_logger

logger = get_logger(__name__)


async def get_redis_connection() -> AsyncGenerator[Redis, None]:
    """
    Создает подключение к Redis.

    Yields:
        Redis: Асинхронное подключение к Redis

    Raises:
        ConnectionError: При ошибке подключения к Redis
    """
    connection = None
    try:
        connection = from_url(
            f"redis://{config.REDIS_HOST}:{config.REDIS_PORT}",
            password=config.REDIS_PASSWORD,
            decode_responses=True,
        )
        logger.debug("Redis connection established")
        yield connection
    except Exception as e:
        logger.error("Failed to connect to Redis: %s", e)
        raise
    finally:
        if connection:
            await connection.aclose()
            logger.debug("Redis connection closed")


RedisDependency = Annotated[Any, Depends(get_redis_connection)]
