"""MCP-сервис Milvus — wiki / векторный поиск."""

from typing import Any

import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from mcp_servers.base import register_health_route, register_tools_route
from mcp_servers.milvus import config

SERVICE_NAME = "mcp-milvus"

TOOLS = [
    {
        "name": "search_documents",
        "description": (
            "Семантический поиск по корпоративной wiki / базе знаний. "
            "Используй для общих вопросов, политик компании, технической документации, "
            "описаний продуктов и любых тем, не связанных с тарифами или коммутаторами."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Поисковый запрос на естественном языке",
                },
                "limit": {
                    "type": "integer",
                    "description": "Максимальное количество документов в ответе (1–50)",
                    "default": 5,
                },
            },
            "required": ["query"],
        },
    }
]

app = FastAPI(
    title="MCP Milvus",
    description="Доменные инструменты для wiki / векторного поиска.",
    version="0.2.0",
)

register_health_route(app, SERVICE_NAME)
register_tools_route(app, TOOLS)


class SearchDocumentsRequest(BaseModel):
    query: str
    limit: int = Field(default=5, ge=1, le=50)


@app.post("/tools/search_documents")
async def search_documents(request: SearchDocumentsRequest) -> dict[str, Any]:
    if not config.MILVUS_SEARCH_URL:
        return {
            "documents": [],
            "combined_context": "",
            "warning": "MILVUS_SEARCH_URL не настроен",
        }

    async with httpx.AsyncClient(timeout=60) as client:
        try:
            response = await client.get(
                config.MILVUS_SEARCH_URL,
                params={"text": request.query, "limit": request.limit},
            )
            response.raise_for_status()
        except httpx.ConnectError as exc:
            return {
                "documents": [],
                "combined_context": "",
                "warning": f"API поиска Milvus недоступен: {exc}",
            }
        except httpx.HTTPStatusError as exc:
            raise HTTPException(
                status_code=502,
                detail=f"API поиска Milvus вернул статус {exc.response.status_code}",
            ) from exc

    payload = response.json()
    combined_context = payload.get("combined_context") or ""
    hashs = payload.get("hashs") or []

    return {
        "combined_context": combined_context,
        "hashs": hashs,
        "documents": (
            [{"text": combined_context, "hashs": hashs}] if combined_context else []
        ),
    }
