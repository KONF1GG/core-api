"""
Схемы данных для AI сервисов.

Содержит Pydantic модели для валидации запросов и ответов
при работе с различными AI моделями.
"""

from typing import Literal
from pydantic import BaseModel, Field


class AIRequest(BaseModel):
    """Модель входных данных для запроса к AI."""

    text: str = Field(..., description="Текст запроса пользователя")
    combined_context: str = Field(..., description="Контекст для обработки запроса")
    chat_history: str = Field(..., description="История предыдущих сообщений в чате")
    input_type: Literal["voice", "csv", "text"] = Field(
        default="text", description="Тип входных данных: голос, CSV файл или текст"
    )
    model: str = Field(
        default="mistral-large-latest",
        description="Название AI модели для обработки запроса",
    )


class AIResponse(BaseModel):
    """Модель ответа от AI системы."""

    ai_response: str = Field(..., description="Ответ от AI модели")

class CategoryRequest(BaseModel):
    """Модель запроса на категорирование"""

    query: str = Field(..., description="Запрос пользователя")


class ClassificationResponse(BaseModel):
    """Модель ответа классификации запроса."""

    category: str = Field(..., description="Категория запроса (Тарифы, Общий, Коммутаторы)")
    address: str | None = Field(None, description="Извлеченный адрес или None")
    raw_response: str | None = Field(None, description="Полный ответ от AI модели")


class SwitcherRequest(BaseModel):
    """Модель запроса для анализа коммутатора."""

    query: str = Field(..., description="Запрос пользователя о коммутаторе")


class SwitcherResponse(BaseModel):
    """Модель ответа анализа коммутатора."""

    analysis: str = Field(..., description="Результат анализа коммутатора")
