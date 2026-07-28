"""HTTP-клиент API redis-adapter."""

from typing import Any, Optional

import aiohttp

from shared.logging import get_logger

logger = get_logger(__name__)


class RedisAdapterError(Exception):
    def __init__(self, message: str, status_code: Optional[int] = None):
        super().__init__(message)
        self.status_code = status_code


class RedisAdapterClient:
    def __init__(self, base_url: str, timeout: int = 100):
        base = base_url.rstrip("/")
        self.api_base = base if base.endswith("/redis") else f"{base}/redis"
        self.timeout = aiohttp.ClientTimeout(total=timeout)

    async def _get(self, endpoint: str, params: dict[str, Any]) -> Any:
        url = f"{self.api_base}/{endpoint.lstrip('/')}"
        async with aiohttp.ClientSession(timeout=self.timeout) as session:
            async with session.get(url, params=params) as response:
                if response.status == 404:
                    if "redis_addresses" in endpoint:
                        logger.debug("Адрес не найден для запроса: %s", params)
                    raise RedisAdapterError(
                        await response.text(), status_code=response.status
                    )
                if response.status >= 400:
                    error_text = await response.text()
                    logger.error(
                        "Ошибка redis-adapter %s: %s", response.status, error_text
                    )
                    raise RedisAdapterError(error_text, status_code=response.status)
                return await response.json()

    async def _post(self, endpoint: str, *, params: dict[str, Any] | None = None, json: dict[str, Any] | None = None) -> Any:
        url = f"{self.api_base}/{endpoint.lstrip('/')}"
        async with aiohttp.ClientSession(timeout=self.timeout) as session:
            async with session.post(url, params=params, json=json) as response:
                if response.status >= 400:
                    error_text = await response.text()
                    logger.error(
                        "Ошибка redis-adapter %s: %s", response.status, error_text
                    )
                    raise RedisAdapterError(error_text, status_code=response.status)
                return await response.json()

    @staticmethod
    def unwrap_result(response: Any) -> Any:
        if isinstance(response, dict) and "result" in response:
            return response["result"]
        return response

    @staticmethod
    def quote_arg(value: str) -> str:
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'

    async def raw_read(self, command: str) -> Any:
        return await self._get("raw", {"query": command})

    async def raw_write(self, command: str) -> Any:
        return await self._post("raw", params={"query": command})

    async def pipeline(self, commands: list[str], atomic: bool = True) -> Any:
        return await self._post(
            "pipeline", json={"commands": commands, "atomic": atomic}
        )

    async def search_addresses(self, query_address: str) -> dict[str, Any]:
        return await self._get("redis_addresses", {"query_address": query_address})

    async def get_address_by_id(self, address_id: str) -> dict[str, Any]:
        return await self._get("redis_address_by_id", {"address_id": address_id})

    async def get_tariffs(self, territory_id: str) -> dict[str, Any]:
        return await self._get("redis_tariffs", {"territory_id": territory_id})


def get_redis_adapter_client(base_url: str | None = None) -> RedisAdapterClient:
    url = (base_url or "").strip()
    if not url:
        raise RedisAdapterError("REDIS_ADAPTER_URL не настроен")
    return RedisAdapterClient(url)
