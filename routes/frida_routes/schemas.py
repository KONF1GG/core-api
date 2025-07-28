"""
Схемы данных для Frida сервисов.

Содержит Pydantic модели для валидации данных аутентификации,
логирования и взаимодействия с внешними системами.
"""

from pydantic import BaseModel, Field
from typing import List, Literal, Optional


class LoggData(BaseModel):
    """Модель данных для логирования запросов пользователей."""

    user_id: int = Field(..., description="ID пользователя в Telegram")
    query: str = Field(..., description="Запрос пользователя")
    ai_response: str = Field(..., description="Ответ AI системы")
    status: Literal[1, 0] = Field(
        ..., description="Статус ответа (1 - успех, 0 - ошибка)"
    )
    hashes: List[str] = Field(..., description="Список хэшей используемых тем")
    category: str = Field(default="", description="Категория запроса")


class UserData(BaseModel):
    """Модель данных пользователя для аутентификации."""

    user_id: int = Field(..., description="ID пользователя в Telegram")
    firstname: str = Field(..., description="Имя пользователя")
    lastname: str = Field(default="", description="Фамилия пользователя")
    username: str = Field(default="", description="Username в Telegram")


class Employee1C(BaseModel):
    """Модель данных сотрудника из системы 1С."""

    fio: str = Field(..., description="ФИО сотрудника")
    jobTitle: str = Field(..., description="Должность сотрудника")


class AuthResponse(BaseModel):
    """Модель ответа для аутентификации пользователя."""

    status: str = Field(..., description="Статус операции (created/exists)")
    message: str = Field(..., description="Сообщение о результате")
    fio: Optional[str] = Field(None, description="ФИО сотрудника")
    position: Optional[str] = Field(None, description="Должность сотрудника")
