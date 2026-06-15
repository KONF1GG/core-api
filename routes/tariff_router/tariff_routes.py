"""
Маршруты для тарифной логики.
"""

from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from logger_config import get_logger
from services import tariff_service
from .schemas import (
    AddressListResponse,
    AddressModel,
    TariffAskRequest,
    TariffAskResponse,
    TariffResolveRequest,
    TariffResolveResponse,
)

router = APIRouter()
logger = get_logger(__name__)


@router.get(
    "/v1/tariff/addresses",
    response_model=AddressListResponse,
    summary="Поиск адресов для тарифов",
    tags=["Tariff"],
)
async def search_tariff_addresses(query: str = Query(..., min_length=1)):
    logger.info("Searching tariff addresses: %s", query)
    addresses = await tariff_service.search_addresses(query)
    return AddressListResponse(addresses=[AddressModel(**a) for a in addresses])


@router.get(
    "/v1/tariff/addresses/{address_id}",
    response_model=AddressModel,
    summary="Получить адрес по ID",
    tags=["Tariff"],
)
async def get_tariff_address(address_id: str):
    logger.info("Getting tariff address by id: %s", address_id)
    address = await tariff_service.get_address_by_id(address_id)
    return AddressModel(**address)


@router.get(
    "/v1/tariff/{territory_id}",
    summary="Получить тарифы для территории",
    tags=["Tariff"],
)
async def get_territory_tariffs(
    territory_id: str,
    conn_types: Optional[list[str]] = Query(None),
):
    logger.info("Getting tariffs for territory: %s", territory_id)
    return await tariff_service.get_tariffs_for_territory(territory_id, conn_types)


@router.post(
    "/v1/tariff/resolve",
    response_model=TariffResolveResponse,
    summary="Резолв адреса из текста запроса",
    tags=["Tariff"],
)
async def resolve_tariff_address(request_data: TariffResolveRequest):
    logger.info("Resolving tariff address for query")
    result = await tariff_service.resolve_address(
        request_data.query, request_data.extracted_address
    )
    address = result.get("address")
    candidates = result.get("candidates")
    return TariffResolveResponse(
        status=result["status"],
        address=AddressModel(**address) if address else None,
        candidates=[AddressModel(**c) for c in candidates] if candidates else None,
    )


@router.post(
    "/v1/tariff/ask",
    response_model=TariffAskResponse,
    summary="Задать вопрос о тарифах с AI-ответом",
    tags=["Tariff"],
)
async def ask_tariff(request_data: TariffAskRequest):
    logger.info("Processing tariff ask for territory: %s", request_data.territory_id)
    try:
        result = await tariff_service.ask_tariff_question(
            query=request_data.query,
            territory_id=request_data.territory_id,
            conn_types=request_data.conn_types,
            chat_history=request_data.chat_history,
            model=request_data.model,
            territory_name=request_data.territory_name,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Unexpected error in ask_tariff: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e

    return TariffAskResponse(**result)
