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


class SwitcherProbeRequest(BaseModel):
    """Запрос диагностики источников данных switcher."""

    ip: str = Field(..., description="IP коммутатора")
    source: Literal["all", "zabbix", "clickhouse", "snmp"] = Field(
        default="all",
        description="Какой источник опрашивать",
    )
    days: int = Field(default=30, ge=1, le=365, description="Глубина выборки FDB в днях")
    snmp_limit: int = Field(default=10, ge=1, le=100, description="Сколько SNMP OID показать в сыром виде")
    row_limit: int = Field(default=30, ge=1, le=500, description="Лимит строк в списках ответа")
    include_context: bool = Field(
        default=False,
        description="Добавить текстовый context из analyze_switch",
    )
    query: str | None = Field(
        default=None,
        description="Текст запроса для analyze_switch (если include_context=true)",
    )


class SwitcherProbeResponse(BaseModel):
    """Ответ диагностики источников данных switcher."""

    switch_ip: str = Field(..., description="IP коммутатора")
    source: str = Field(..., description="Опрошенный источник")
    config: dict = Field(..., description="Конфигурация подключений (без секретов)")
    zabbix: dict | None = Field(default=None, description="Данные Zabbix")
    clickhouse: dict | None = Field(default=None, description="Данные ClickHouse")
    snmp: dict | None = Field(default=None, description="Данные SNMP")
    context: str | None = Field(default=None, description="Контекст analyze_switch")
