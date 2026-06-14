"""
Маршруты для взаимодействия с AI сервисами.

Предоставляет API для отправки запросов к различным AI моделям
с поддержкой разных типов входных данных и автоматическим переключением моделей.
"""

from fastapi import APIRouter, HTTPException

from ai import get_ai, classify_query
from config import PROMPT_SWITCHER
from logger_config import get_logger
from switcher import analyze_switch
from .schmeas import (
    AIRequest,
    AIResponse,
    CategoryRequest,
    ClassificationResponse,
    SwitcherRequest,
    SwitcherResponse,
)

router = APIRouter()
logger = get_logger(__name__)


@router.post(
    "/v1/ai",
    response_model=AIResponse,
    summary="Получить ответ от модели AI",
    description=(
        "Отправляет запрос к модели AI с специализированным промтом "
        "для фриды и возвращает ответ"
    ),
    tags=["AI"],
)
async def get_ai_response(request_data: AIRequest):
    """
    Обрабатывает запрос к AI модели.

    Args:
        request_data: Данные запроса (текст, контекст, история, тип ввода, модель)

    Returns:
        AIResponse: Ответ от AI модели

    Raises:
        HTTPException: При ошибках обработки запроса или недоступности модели
    """
    try:
        logger.info(
            "Processing AI request: model=%s, input_type=%s",
            request_data.model,
            request_data.input_type,
        )

        response_text = await get_ai(
            request_data.text,
            request_data.combined_context,
            request_data.chat_history,
            request_data.input_type,
            request_data.model,
        )

        logger.info("AI request processed successfully")
        return AIResponse(ai_response=response_text)

    except HTTPException:
        # Перебрасываем HTTPException без изменений
        raise
    except Exception as e:
        logger.error("Unexpected error in get_ai_response: %s", e, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "status": "error",
                "message": "Internal server error",
                "error": str(e),
            },
        ) from e


@router.post(
    "/v1/category",
    response_model=ClassificationResponse,
    summary="Определить категорию запроса",
    description="Классифицирует запрос пользователя с помощью AI и определяет категорию (Тарифы, Общий, Коммутаторы) и извлекает адрес если есть",
    tags=["AI"],
)
async def get_classify_query(request_data: CategoryRequest):
    """
    Классифицирует запрос пользователя.

    Args:
        request_data: Данные запроса с текстом для классификации

    Returns:
        ClassificationResponse: Результат классификации с категорией и адресом
    """
    try:
        logger.info("Processing classification request")
        result = await classify_query(request_data)
        logger.info(f"Classification result: category={result['category']}, address={result['address']}")
        return ClassificationResponse(**result)
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Unexpected error in get_classify_query: %s", e, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "status": "error",
                "message": "Internal server error",
                "error": str(e),
            },
        ) from e


@router.post(
    "/v1/switcher",
    response_model=SwitcherResponse,
    summary="Анализ коммутатора",
    description="Анализирует коммутатор и рассчитывает свободные порты на основе данных из Zabbix, ClickHouse и SNMP",
    tags=["AI"],
)
async def analyze_switcher(request_data: SwitcherRequest):
    """
    Анализирует коммутатор и рассчитывает свободные порты.

    Args:
        request_data: Данные запроса с текстом о коммутаторе

    Returns:
        SwitcherResponse: Результат анализа коммутатора
    """
    try:
        logger.info("Processing switcher analysis request")

        # Собираем данные из разных источников
        context = await analyze_switch(request_data.query)

        # Формируем промт для AI
        prompt = PROMPT_SWITCHER.format(
            context=context,
            query=request_data.query
        )

        # Отправляем в AI для анализа
        analysis_result = await get_ai(
            query=prompt,
            context="",
            history="",
            input_type="text",
            model="mistral-large-latest",
        )

        logger.info("Switcher analysis completed successfully")
        return SwitcherResponse(analysis=analysis_result)

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Unexpected error in analyze_switcher: %s", e, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "status": "error",
                "message": "Internal server error",
                "error": str(e),
            },
        ) from e