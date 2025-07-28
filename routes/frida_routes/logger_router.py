"""Маршруты для логирования сообщений в базу данных Frida."""

from fastapi import APIRouter, HTTPException

import config
from databases import PostgreSQL
from general_schemas import StatusResponse
from logger_config import get_logger
from .schemas import LoggData

router = APIRouter()
logger = get_logger(__name__)


@router.post("/v1/log", tags=["Frida"])
async def log_to_frida_db(data: LoggData) -> StatusResponse:
    """
    Логирует сообщение в базу данных Frida.

    Args:
        data: Данные для логирования (запрос, ответ, статус, хэши, категория)

    Returns:
        StatusResponse: Статус выполнения операции

    Raises:
        HTTPException: При ошибках записи в базу данных
    """
    logger.info("Logging message for user: %s", data.user_id)
    postgres = None

    try:
        postgres = PostgreSQL(**config.postgres_config)
        postgres.log_message(
            data.user_id,
            data.query,
            data.ai_response,
            data.status == 1,
            data.hashes,
            data.category,
        )

        logger.debug("Message logged successfully for user: %s", data.user_id)
        return StatusResponse(status="success")

    except Exception as e:
        logger.error(
            "Failed to log message for user %s: %s", data.user_id, e, exc_info=True
        )
        raise HTTPException(status_code=500, detail="Internal server error") from e
    finally:
        if postgres:
            postgres.connection_close()
