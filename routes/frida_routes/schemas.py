"""
Схемы данных для Frida сервисов.

Содержит Pydantic модели для валидации данных аутентификации,
логирования и взаимодействия с внешними системами.
"""
from typing import List, Literal
from pydantic import BaseModel, Field


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
    source_type: str = Field(default="", description="Откуда пришел запрос")


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


class AuthResponse(Employee1C):
    """Модель ответа для аутентификации пользователя."""
