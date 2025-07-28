"""
Маршруты для взаимодействия с AI сервисами.

Предоставляет API для отправки запросов к различным AI моделям
с поддержкой разных типов входных данных и автоматическим переключением моделей.
"""

from fastapi import APIRouter, HTTPException

from ai import get_ai
from logger_config import get_logger
from .schmeas import AIRequest, AIResponse

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
