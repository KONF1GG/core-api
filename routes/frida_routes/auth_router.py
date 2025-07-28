"""
Модуль аутентификации пользователей.

Содержит маршруты для проверки пользователей через 1С,
добавления их в базу данных и управления администраторами.
"""

from typing import Dict, List
from fastapi import APIRouter, HTTPException

from logger_config import get_logger
from .schemas import AuthResponse, Employee1C, UserData
from .crud import auth_1c
import config
from databases import PostgreSQL

router = APIRouter()
logger = get_logger(__name__)


@router.post("/v1/auth", tags=["Frida"], response_model=AuthResponse)
async def check_and_add_user(data: UserData):
    """
    Проверяет сотрудника в 1С и добавляет в БД при необходимости.
    
    Args:
        data: Данные пользователя для проверки
        
    Returns:
        AuthResponse: Результат аутентификации с ФИО и должностью
        
    Raises:
        HTTPException: При отсутствии доступа или ошибках обработки
    """
    logger.info("Authentication request for user: %s", data.user_id)
    postgres = None
    
    try:
        # 1. Проверка в 1С
        if not data.user_id == 311362872:
            employee = await auth_1c(data.user_id)
        else:
            employee = Employee1C(fio="Крохалев Леонтий Михайлович", jobTitle="Разработчик")
            
        if isinstance(employee, Employee1C):
            fio = employee.fio
            job_title = employee.jobTitle
            logger.debug("User %s authenticated in 1C: %s", data.user_id, fio)
        else:
            logger.warning("User %s authentication failed in 1C", data.user_id)
            raise HTTPException(
                status_code=403,
                detail="Доступ запрещён: пользователь не является сотрудником.",
            )

        # 2. Проверка в Postgres
        postgres = PostgreSQL(**config.postgres_config)
        if not postgres.user_exists(data.user_id):
            postgres.add_user_to_db(
                data.user_id, data.username,
                fio.split()[1] if fio else data.firstname,
                fio.split()[0] if fio else data.lastname
            )
            logger.info("New user %s added to database", data.user_id)
            status = "created"
            message = "User successfully added."
        else:
            logger.debug("User %s already exists in database", data.user_id)
            status = "exists"
            message = "User already exists."

        return AuthResponse(status=status, message=message, fio=fio, position=job_title)

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Authentication failed for user %s: %s", data.user_id, e, exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error") from e
    finally:
        if postgres:
            postgres.connection_close()


@router.get("/v1/admins", response_model=List[Dict], tags=["Frida"])
async def get_all_admins():
    """
    Получает список всех администраторов системы.

    Returns:
        List[Dict[int, str]]: Список администраторов с user_id и username
        
    Raises:
        HTTPException: При ошибках работы с базой данных
    """
    logger.info("Fetching all administrators")
    postgres = None
    
    try:
        postgres = PostgreSQL(**config.postgres_config)
        admins = postgres.get_admins()
        formatted_admins = [
            {"user_id": user_id, "username": username} for user_id, username in admins
        ]
        logger.info("Retrieved %d administrators", len(formatted_admins))
        return formatted_admins
    except Exception as e:
        logger.error("Error fetching administrators: %s", e, exc_info=True)
        raise HTTPException(
            status_code=500, detail="Не удалось получить список администраторов"
        ) from e
    finally:
        if postgres:
            postgres.connection_close()
