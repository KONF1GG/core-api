"""Доменная логика mcp-tariff."""

from typing import Any, Literal, Optional

import aiohttp
from fastapi import HTTPException

from mcp_servers.tariff import config
from mcp_servers.tariff.services.address_client import extract_house_id
from shared.redis_adapter_client import RedisAdapterError, get_redis_adapter_client
from shared.logging import get_logger

logger = get_logger(__name__)

ResolveStatus = Literal["ready", "need_confirmation", "not_found", "no_address"]


def _resolve_result(
    address: dict[str, Any],
    candidates: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    if candidates and len(candidates) > 1:
        return {
            "status": "need_confirmation",
            "address": address,
            "candidates": candidates,
        }
    return {
        "status": "ready",
        "address": address,
        "candidates": None,
    }


def filter_tariffs_by_conn_type(
    tariff_info: dict[str, Any], conn_types: Optional[list[str]]
) -> dict[str, Any]:
    if not conn_types or not isinstance(tariff_info, dict):
        return tariff_info

    filtered: dict[str, Any] = {}
    for conn_type in conn_types:
        if conn_type in tariff_info:
            filtered[conn_type] = tariff_info[conn_type]

    if filtered:
        logger.info("Тарифы отфильтрованы по conn_types: %s", conn_types)
        return filtered

    logger.warning("Тарифы не найдены для conn_types: %s", conn_types)
    return tariff_info


def _normalize_address(raw: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": raw.get("id"),
        "address": raw.get("address", ""),
        "territory_id": str(raw.get("territory_id", "")),
        "territory_name": raw.get("territory_name", ""),
        "conn_type": raw.get("conn_type") or [],
    }


def _get_redis_adapter_client():
    if not config.REDIS_ADAPTER_URL:
        logger.warning("REDIS_ADAPTER_URL не настроен")
        return None
    return get_redis_adapter_client(config.REDIS_ADAPTER_URL)


async def search_addresses(query: str) -> list[dict[str, Any]]:
    client = _get_redis_adapter_client()
    if client is None:
        return []

    try:
        data = await client.search_addresses(query)
    except RedisAdapterError as e:
        if e.status_code == 404:
            return []
        raise HTTPException(status_code=502, detail=str(e)) from e
    except aiohttp.ClientError as e:
        logger.error("Redis-адаптер недоступен: %s", e)
        return []

    addresses = data.get("addresses", [])
    if not isinstance(addresses, list):
        return []
    return [_normalize_address(item) for item in addresses]


async def get_address_by_id(address_id: str) -> dict[str, Any]:
    client = _get_redis_adapter_client()
    if client is None:
        raise HTTPException(status_code=503, detail="REDIS_ADAPTER_URL не настроен")

    try:
        data = await client.get_address_by_id(address_id)
    except RedisAdapterError as e:
        if e.status_code == 404:
            raise HTTPException(status_code=404, detail="Адрес не найден") from e
        raise HTTPException(status_code=502, detail=str(e)) from e
    return _normalize_address(data)


async def get_tariffs_for_territory(
    territory_id: str, conn_types: Optional[list[str]] = None
) -> dict[str, Any]:
    client = _get_redis_adapter_client()
    if client is None:
        raise HTTPException(status_code=503, detail="REDIS_ADAPTER_URL не настроен")

    try:
        tariff_info = await client.get_tariffs(territory_id)
    except RedisAdapterError as e:
        if e.status_code == 404:
            raise HTTPException(status_code=404, detail="Тарифы не найдены") from e
        raise HTTPException(status_code=502, detail=str(e)) from e

    return filter_tariffs_by_conn_type(tariff_info, conn_types)


async def resolve_address(
    query: str, extracted_address: Optional[str] = None
) -> dict[str, Any]:
    house_id = await extract_house_id(query)

    if house_id:
        try:
            address = await get_address_by_id(house_id)
        except HTTPException:
            address = None
        else:
            if address.get("territory_id"):
                return _resolve_result(address)

    if extracted_address:
        candidates = await search_addresses(extracted_address)
        if candidates:
            first = candidates[0]
            if first.get("territory_id"):
                return _resolve_result(
                    first,
                    candidates if len(candidates) > 1 else None,
                )
        return {
            "status": "not_found",
            "address": None,
            "candidates": candidates or None,
        }

    return {"status": "no_address", "address": None, "candidates": None}
