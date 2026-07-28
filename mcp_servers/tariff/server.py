"""MCP-сервис тарифов — разрешение адресов и доступ к тарифным данным."""

from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from mcp_servers.base import register_health_route, register_tools_route
from mcp_servers.tariff.services import tariff_service

SERVICE_NAME = "mcp-tariff"

TOOLS = [
    {
        "name": "resolve_address",
        "description": (
            "Разрешает адресную строку пользователя в структурированный адрес с territory_id. "
            "Всегда вызывай ПЕРВЫМ, когда пользователь спрашивает о тарифах или стоимости "
            "подключения по конкретному адресу. При одном найденном адресе возвращает "
            "status='ready' — сразу вызывай get_tariffs. Если несколько candidates — "
            "status='need_confirmation', предложи варианты и дождись выбора пользователя."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Полное сообщение пользователя, содержащее адрес",
                },
                "extracted_address": {
                    "type": "string",
                    "description": (
                        "Адресная строка, извлечённая из запроса, "
                        "например 'ул. Ленина 5, Челябинск'"
                    ),
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "get_tariffs",
        "description": (
            "Возвращает доступные интернет-тарифы для территории. "
            "Передай address и territory_name из resolve_address — они вернутся в ответе, "
            "чтобы указать пользователю, для какого адреса и территории показаны тарифы."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "territory_id": {
                    "type": "string",
                    "description": "Идентификатор территории из resolve_address",
                },
                "address": {
                    "type": "string",
                    "description": "Адрес из resolve_address (поле address)",
                },
                "territory_name": {
                    "type": "string",
                    "description": "Название территории из resolve_address",
                },
                "conn_types": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Необязательный список типов подключения для фильтрации",
                },
            },
            "required": ["territory_id"],
        },
    },
]

app = FastAPI(
    title="MCP Tariff",
    description="Доменные инструменты для работы с тарифами и адресами.",
    version="0.2.0",
)

register_health_route(app, SERVICE_NAME)
register_tools_route(app, TOOLS)


class ResolveAddressRequest(BaseModel):
    query: str
    extracted_address: str | None = None


class GetTariffsRequest(BaseModel):
    territory_id: str
    address: str | None = None
    territory_name: str | None = None
    conn_types: list[str] | None = None


@app.post("/tools/resolve_address")
async def resolve_address(request: ResolveAddressRequest) -> dict[str, Any]:
    return await tariff_service.resolve_address(
        query=request.query,
        extracted_address=request.extracted_address,
    )


@app.post("/tools/get_tariffs")
async def get_tariffs(request: GetTariffsRequest) -> dict[str, Any]:
    try:
        tariffs = await tariff_service.get_tariffs_for_territory(
            request.territory_id,
            request.conn_types,
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return {
        "territory_id": request.territory_id,
        "address": request.address,
        "territory_name": request.territory_name,
        "tariffs": tariffs,
    }
