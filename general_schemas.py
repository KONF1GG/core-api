"""
Общие схемы данных для всего приложения.

Содержит базовые Pydantic модели, используемые в различных модулях.
"""

from typing import Literal
from pydantic import BaseModel, Field


class StatusResponse(BaseModel):
    """Стандартная модель ответа с указанием статуса выполнения операции."""

    status: Literal["success", "error"] = Field(
        ..., description="Статус выполнения операции"
    )
