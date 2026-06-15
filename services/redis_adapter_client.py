"""
HTTP-клиент для redis-adapter API.
"""

from typing import Any, Optional

import aiohttp

import config
from logger_config import get_logger

logger = get_logger(__name__)


class RedisAdapterError(Exception):
    """Ошибка при обращении к redis-adapter."""

    def __init__(self, message: str, status_code: Optional[int] = None):
        super().__init__(message)
        self.status_code = status_code


class RedisAdapterClient:
    def __init__(self, base_url: str, timeout: int = 100):
        self.base_url = base_url.rstrip("/")
        self.timeout = aiohttp.ClientTimeout(total=timeout)

    async def _get(self, endpoint: str, params: dict[str, Any]) -> Any:
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        async with aiohttp.ClientSession(timeout=self.timeout) as session:
            async with session.get(url, params=params) as response:
                if response.status == 404:
                    if "redis_addresses" in endpoint:
                        logger.debug("Address not found for query: %s", params)
                    raise RedisAdapterError(
                        await response.text(), status_code=response.status
                    )
                if response.status >= 400:
                    error_text = await response.text()
                    logger.error(
                        "Redis adapter error %s: %s", response.status, error_text
                    )
                    raise RedisAdapterError(error_text, status_code=response.status)
                return await response.json()

    async def search_addresses(self, query_address: str) -> dict[str, Any]:
        return await self._get("redis_addresses", {"query_address": query_address})

    async def get_address_by_id(self, address_id: str) -> dict[str, Any]:
        return await self._get("redis_address_by_id", {"address_id": address_id})

    async def get_tariffs(self, territory_id: str) -> dict[str, Any]:
        return await self._get("redis_tariffs", {"territory_id": territory_id})


def get_redis_adapter_client() -> RedisAdapterClient:
    if not config.REDIS_ADAPTER_URL:
        raise RedisAdapterError("REDIS_ADAPTER_URL is not configured")
    return RedisAdapterClient(config.REDIS_ADAPTER_URL)
