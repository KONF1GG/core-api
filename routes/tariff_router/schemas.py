"""
Схемы данных для тарифных эндпоинтов.
"""

from typing import Literal, Optional

from pydantic import BaseModel, Field


class AddressModel(BaseModel):
    id: Optional[int] = None
    address: str = ""
    territory_id: str = ""
    territory_name: str = ""
    conn_type: list[str] = Field(default_factory=list)


class AddressListResponse(BaseModel):
    addresses: list[AddressModel]


class TariffResolveRequest(BaseModel):
    query: str = Field(..., description="Запрос пользователя")
    extracted_address: Optional[str] = Field(
        None, description="Адрес, извлечённый классификатором"
    )


class TariffResolveResponse(BaseModel):
    status: Literal["need_confirmation", "ready", "not_found", "no_address"]
    address: Optional[AddressModel] = None
    candidates: Optional[list[AddressModel]] = None


class TariffAskRequest(BaseModel):
    query: str = Field(..., description="Вопрос пользователя о тарифах")
    territory_id: str = Field(..., description="ID территории")
    conn_types: Optional[list[str]] = Field(None, description="Типы подключения для фильтрации")
    territory_name: Optional[str] = None
    chat_history: str = ""
    model: str = "mistral-large-latest"


class TariffAskResponse(BaseModel):
    answer: str
    territory_id: str
    territory_name: Optional[str] = None
