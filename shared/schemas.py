"""Общие API-схемы для клиентов и платформенных сервисов."""

from typing import Any, Literal

from pydantic import BaseModel, Field


ClientSource = Literal["telegram", "max", "web", "api"]


class ChatRequest(BaseModel):
    """Запрос к единой точке входа клиента."""

    user_id: str = Field(..., description="Идентификатор пользователя на платформе")
    message: str = Field(..., min_length=1, description="Сообщение пользователя")
    session_id: str = Field(..., description="Идентификатор диалога/сессии")
    source: ClientSource = Field(default="api", description="Источник клиента")
    input_type: Literal["text", "voice", "csv"] = Field(default="text")
    model: str | None = Field(default=None, description="Предпочитаемая LLM-модель")


class ToolCallRecord(BaseModel):
    """Запись об одном вызове инструмента агентом."""

    name: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    result: Any | None = None
    error: str | None = None


class ChatResponse(BaseModel):
    """Единый ответ, возвращаемый тонким клиентам."""

    text: str
    session_id: str
    source: ClientSource
    tool_calls: list[ToolCallRecord] = Field(default_factory=list)
    model: str | None = None
