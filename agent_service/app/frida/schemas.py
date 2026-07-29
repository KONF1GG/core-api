"""Схемы Frida (auth, admins)."""

from typing import Optional

from pydantic import BaseModel, Field


class UserData(BaseModel):
    user_id: int = Field(..., description="ID пользователя в Telegram")
    firstname: str = Field(..., description="Имя пользователя")
    lastname: str = Field(default="", description="Фамилия пользователя")
    username: str = Field(default="", description="Username в Telegram")


class Employee1C(BaseModel):
    fio: str = Field(..., description="ФИО сотрудника")
    jobTitle: str = Field(..., description="Должность сотрудника")


class AuthResponse(BaseModel):
    status: str = Field(..., description="Статус операции (created/exists)")
    message: str = Field(..., description="Сообщение о результате")
    fio: Optional[str] = Field(None, description="ФИО сотрудника")
    position: Optional[str] = Field(None, description="Должность сотрудника")


class UploadWikiRequest(BaseModel):
    user_id: int = Field(..., description="ID пользователя, инициирующего загрузку")


class UploadWikiResponse(BaseModel):
    status: str
    message: str
    data: Optional[dict] = None
