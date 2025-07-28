"""
Схемы данных для Redis операций.

Содержит Pydantic модели для валидации данных адресов,
территорий и тарифов при работе с Redis.
"""

from typing import List, Optional
from pydantic import BaseModel, Field


class RedisAddressModel(BaseModel):
    """Модель адреса для поиска тарифов в системе Frida."""

    id: int = Field(..., description="Уникальный идентификатор адреса (adds:id)")
    address: str = Field(..., description="Название адреса")
    territory_id: str = Field(..., description="Идентификатор территории")
    territory_name: str = Field(..., description="Название территории")
    conn_type: Optional[List[str]] = Field(None, description="Типы подключения")


class RedisAddressModelResponse(BaseModel):
    """Модель ответа для запроса списка адресов."""

    addresses: List[RedisAddressModel] = Field(
        ..., description="Список найденных адресов"
    )
