"""HTTP-агрегатор доменных MCP-сервисов."""

import time
from typing import Any

import httpx

from agent_service.app import config
from shared.log_helpers import fmt_json, summarize_tool_result, truncate
from shared.logging import get_logger

logger = get_logger(__name__)


class MCPAggregator:
    """Вызывает доменные инструменты MCP-сервисов по HTTP."""

    def __init__(self, timeout: float = 60.0):
        self.timeout = timeout
        self.services = {
            "tariff": config.MCP_TARIFF_URL.rstrip("/"),
            "switcher": config.MCP_SWITCHER_URL.rstrip("/"),
            "milvus": config.MCP_MILVUS_URL.rstrip("/"),
        }

    async def health(self) -> dict[str, Any]:
        """Проверяет доступность всех настроенных MCP-сервисов."""
        status: dict[str, Any] = {}
        async with httpx.AsyncClient(timeout=10.0) as client:
            for service_name, base_url in self.services.items():
                try:
                    response = await client.get(f"{base_url}/health")
                    response.raise_for_status()
                    status[service_name] = {"ok": True, **response.json()}
                except httpx.HTTPError as exc:
                    logger.warning("MCP-сервис %s недоступен: %s", service_name, exc)
                    status[service_name] = {"ok": False, "error": str(exc)}
        return status

    async def list_tools(self) -> list[dict[str, Any]]:
        """Собирает сырые описания инструментов со всех MCP-сервисов."""
        tools: list[dict[str, Any]] = []
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            for service_name, base_url in self.services.items():
                try:
                    response = await client.get(f"{base_url}/tools")
                    response.raise_for_status()
                    for tool in response.json().get("tools", []):
                        tool["service"] = service_name
                        tools.append(tool)
                except httpx.HTTPError as exc:
                    logger.warning(
                        "[mcp:tools] %s (%s) недоступен: %s",
                        service_name,
                        base_url,
                        exc,
                    )
        tool_names = [f"{t.get('service')}.{t.get('name')}" for t in tools]
        logger.info(
            "[mcp:tools] загружено %d инструментов: %s",
            len(tools),
            ", ".join(tool_names) or "—",
        )
        return tools

    async def list_tools_for_llm(self) -> list[dict[str, Any]]:
        """
        Возвращает инструменты в формате function calling для Mistral.

        Имена функций кодируются через двойное подчёркивание:
            "<service>__<tool_name>", например "tariff__resolve_address"
        чтобы их можно было декодировать через parse_tool_name().
        """
        raw = await self.list_tools()
        return [_to_mistral_tool(t) for t in raw]

    async def call_tool(
        self,
        service: str,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> Any:
        if service not in self.services:
            raise ValueError(f"Неизвестный MCP-сервис: {service!r}")

        base_url = self.services[service]
        url = f"{base_url}/tools/{tool_name}"
        logger.info(
            "[mcp:call] → POST %s args=%s",
            url,
            fmt_json(arguments, 300),
        )
        started = time.monotonic()
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.post(url, json=arguments)
                duration_ms = int((time.monotonic() - started) * 1000)
                response.raise_for_status()
                result = response.json()
                logger.info(
                    "[mcp:call] ← %s.%s HTTP %s %dms | %s",
                    service,
                    tool_name,
                    response.status_code,
                    duration_ms,
                    summarize_tool_result(service, tool_name, result),
                )
                return result
            except httpx.HTTPStatusError as exc:
                duration_ms = int((time.monotonic() - started) * 1000)
                body = truncate(exc.response.text, 200)
                logger.error(
                    "[mcp:call] ← %s.%s HTTP %s %dms body=%r",
                    service,
                    tool_name,
                    exc.response.status_code,
                    duration_ms,
                    body,
                )
                raise
            except httpx.HTTPError as exc:
                duration_ms = int((time.monotonic() - started) * 1000)
                logger.error(
                    "[mcp:call] ← %s.%s ошибка сети %dms: %s",
                    service,
                    tool_name,
                    duration_ms,
                    exc,
                )
                raise


def _to_mistral_tool(raw: dict[str, Any]) -> dict[str, Any]:
    """Преобразует описание инструмента в формат function calling Mistral."""
    service = raw.get("service", "unknown")
    name = raw.get("name", "unknown")
    fn_name = f"{service}__{name}"

    parameters = raw.get("parameters") or {
        "type": "object",
        "properties": {},
        "required": [],
    }

    return {
        "type": "function",
        "function": {
            "name": fn_name,
            "description": raw.get("description", ""),
            "parameters": parameters,
        },
    }


def parse_tool_name(fn_name: str) -> tuple[str, str]:
    """
    Декодирует имя функции Mistral обратно в (service, tool_name).

    "tariff__resolve_address" -> ("tariff", "resolve_address")
    """
    if "__" in fn_name:
        service, tool = fn_name.split("__", 1)
        return service, tool
    raise ValueError(f"Не удалось разобрать имя инструмента: {fn_name!r}")
