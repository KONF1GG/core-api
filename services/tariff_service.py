"""
Сервисный слой тарифной логики.
"""

from typing import Any, Literal, Optional

from fastapi import HTTPException

from ai import get_ai
from logger_config import get_logger
from services.address_client import extract_house_id
from services.redis_adapter_client import (
    RedisAdapterError,
    get_redis_adapter_client,
)

logger = get_logger(__name__)

ResolveStatus = Literal["need_confirmation", "ready", "not_found", "no_address"]


def filter_tariffs_by_conn_type(
    tariff_info: dict[str, Any], conn_types: Optional[list[str]]
) -> dict[str, Any]:
    """Фильтрует тарифы по доступным типам подключения."""
    if not conn_types or not isinstance(tariff_info, dict):
        return tariff_info

    filtered: dict[str, Any] = {}
    for conn_type in conn_types:
        if conn_type in tariff_info:
            filtered[conn_type] = tariff_info[conn_type]

    if filtered:
        logger.info("Filtered tariffs for conn_types: %s", conn_types)
        return filtered

    logger.warning("No tariffs found for conn_types: %s", conn_types)
    return tariff_info


def build_tariff_context(
    territory_id: str, territory_name: str, tariff_info: Any
) -> str:
    """Собирает строку контекста для AI."""
    name_part = f" ({territory_name})" if territory_name else ""
    return (
        f"Информация о тарифах для территории {territory_id}{name_part}:\n{tariff_info}"
    )


def _normalize_address(raw: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": raw.get("id"),
        "address": raw.get("address", ""),
        "territory_id": str(raw.get("territory_id", "")),
        "territory_name": raw.get("territory_name", ""),
        "conn_type": raw.get("conn_type") or [],
    }


async def search_addresses(query: str) -> list[dict[str, Any]]:
    """Поиск адресов по строке запроса."""
    client = get_redis_adapter_client()
    try:
        data = await client.search_addresses(query)
    except RedisAdapterError as e:
        if e.status_code == 404:
            return []
        raise HTTPException(status_code=502, detail=str(e)) from e

    addresses = data.get("addresses", [])
    if not isinstance(addresses, list):
        return []
    return [_normalize_address(item) for item in addresses]


async def get_address_by_id(address_id: str) -> dict[str, Any]:
    """Получает адрес по house_id."""
    client = get_redis_adapter_client()
    try:
        data = await client.get_address_by_id(address_id)
    except RedisAdapterError as e:
        if e.status_code == 404:
            raise HTTPException(status_code=404, detail="Address not found") from e
        raise HTTPException(status_code=502, detail=str(e)) from e
    return _normalize_address(data)


async def get_tariffs_for_territory(
    territory_id: str, conn_types: Optional[list[str]] = None
) -> dict[str, Any]:
    """Получает тарифы для территории с опциональной фильтрацией."""
    client = get_redis_adapter_client()
    try:
        tariff_info = await client.get_tariffs(territory_id)
    except RedisAdapterError as e:
        if e.status_code == 404:
            raise HTTPException(status_code=404, detail="Tariffs not found") from e
        raise HTTPException(status_code=502, detail=str(e)) from e

    return filter_tariffs_by_conn_type(tariff_info, conn_types)


async def resolve_address(
    query: str, extracted_address: Optional[str] = None
) -> dict[str, Any]:
    """
    Резолвит адрес из текста запроса.

    Returns:
        dict с полями status, address, candidates
    """
    house_id = await extract_house_id(query)

    if house_id:
        try:
            address = await get_address_by_id(house_id)
        except HTTPException:
            address = None
        else:
            if address.get("territory_id"):
                return {
                    "status": "need_confirmation",
                    "address": address,
                    "candidates": None,
                }

    if extracted_address:
        candidates = await search_addresses(extracted_address)
        if candidates:
            first = candidates[0]
            if first.get("territory_id"):
                return {
                    "status": "ready",
                    "address": first,
                    "candidates": candidates,
                }
        return {
            "status": "not_found",
            "address": None,
            "candidates": candidates or None,
        }

    return {"status": "no_address", "address": None, "candidates": None}


async def ask_tariff_question(
    query: str,
    territory_id: str,
    conn_types: Optional[list[str]] = None,
    chat_history: str = "",
    model: str = "mistral-large-latest",
    territory_name: Optional[str] = None,
) -> dict[str, Any]:
    """Получает тарифы, собирает контекст и возвращает AI-ответ."""
    tariff_info = await get_tariffs_for_territory(territory_id, conn_types)
    tariff_context = build_tariff_context(
        territory_id, territory_name or "", tariff_info
    )

    answer = await get_ai(
        query=query,
        context=tariff_context,
        history=chat_history,
        input_type="text",
        model=model,
    )

    return {
        "answer": answer,
        "territory_id": territory_id,
        "territory_name": territory_name,
    }
