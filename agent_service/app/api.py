"""HTTP API Agent Service."""

from typing import Any

from fastapi import APIRouter, HTTPException

from agent_service.app.agent.executor import AgentExecutor
from agent_service.app.mcp.aggregator import MCPAggregator
from shared.logging import get_logger
from shared.schemas import ChatRequest, ChatResponse

logger = get_logger(__name__)
router = APIRouter(prefix="/v1", tags=["Agent"])
_mcp = MCPAggregator()


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    """Единая точка чата для клиентов Telegram, Max и Web."""
    try:
        return await AgentExecutor(mcp=_mcp).run(request)
    except HTTPException as exc:
        logger.warning(
            "[api:chat] HTTP %s user_id=%s session=%s detail=%s",
            exc.status_code,
            request.user_id,
            request.session_id,
            exc.detail,
        )
        raise
    except Exception as exc:
        logger.error(
            "[api:chat] 500 user_id=%s session=%s: %s",
            request.user_id,
            request.session_id,
            exc,
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/tools")
async def list_tools() -> dict[str, Any]:
    """Список MCP-инструментов (для отладки и интроспекции)."""
    tools = await _mcp.list_tools()
    return {"tools": tools, "count": len(tools)}


@router.get("/mcp/health")
async def mcp_health() -> dict[str, Any]:
    """Проверка доступности всех настроенных MCP-сервисов."""
    status = await _mcp.health()
    all_ok = all(item.get("ok") for item in status.values())
    return {"status": "healthy" if all_ok else "degraded", "services": status}
