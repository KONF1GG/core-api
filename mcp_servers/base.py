"""Общие хелперы для доменных MCP HTTP-сервисов."""

from typing import Any

from fastapi import FastAPI, HTTPException


def register_health_route(app: FastAPI, service_name: str) -> None:
    @app.get("/health")
    async def health_check():
        return {"status": "healthy", "service": service_name}


def register_tools_route(app: FastAPI, tools: list[dict[str, Any]]) -> None:
    @app.get("/tools")
    async def list_tools():
        return {"tools": tools}


def tool_not_found(tool_name: str) -> HTTPException:
    return HTTPException(status_code=404, detail=f"Неизвестный инструмент: {tool_name}")
