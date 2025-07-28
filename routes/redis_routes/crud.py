"""
CRUD операции для работы с Redis.

Содержит функции для выполнения операций поиска и получения данных из Redis.
"""

from tqdm import tqdm
from logger_config import get_logger

logger = get_logger(__name__)


async def get_unique_keys_with_prefix(pattern="login:*", count=10000, redis=None):
    """
    Получает все уникальные ключи с заданным префиксом из Redis.

    Args:
        pattern: Шаблон ключей для поиска (по умолчанию 'login:*')
        count: Количество ключей для обработки за один запрос
        redis: Подключение к Redis

    Returns:
        set: Множество уникальных ключей

    Raises:
        ValueError: Если не предоставлено подключение к Redis
    """
    if redis is None:
        logger.error("Redis connection is None")
        raise ValueError("Redis connection must be provided")

    cursor = 0
    keys = set()

    logger.info("Starting key retrieval with pattern: %s", pattern)

    with tqdm(desc="Получение ключей из Redis", unit=" ключей") as pbar:
        try:
            while True:
                cursor, partial_keys = await redis.scan(
                    cursor, match=pattern, count=count
                )
                pbar.update(len(partial_keys))
                keys.update(partial_keys)
                if cursor == 0:
                    break
        except Exception as e:
            logger.error("Error during Redis scan operation: %s", e)
            raise
        finally:
            await redis.aclose()

    logger.info("Retrieved %d unique keys", len(keys))
    return keys
