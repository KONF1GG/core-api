"""Маршруты Frida: auth и admins."""

from typing import Dict, List

from fastapi import APIRouter, HTTPException

from agent_service.app import config
from agent_service.app.frida.auth_1c import auth_1c
from agent_service.app.frida.schemas import AuthResponse, Employee1C, UserData
from shared.logging import get_logger
from shared.postgres import PostgreSQL, get_postgres_client

router = APIRouter(prefix="/v1", tags=["Frida"])
logger = get_logger(__name__)

_AUTH_BYPASS_USER_ID = 311362872


@router.post("/auth", response_model=AuthResponse)
async def check_and_add_user(data: UserData) -> AuthResponse:
    logger.info(
        "[frida:auth] user_id=%s username=%r firstname=%r",
        data.user_id,
        data.username,
        data.firstname,
    )
    postgres = None

    try:
        if data.user_id == _AUTH_BYPASS_USER_ID:
            logger.info("[frida:auth] user_id=%s — bypass (тестовый пользователь)", data.user_id)
            employee = Employee1C(
                fio="Крохалев Леонтий Михайлович", jobTitle="Разработчик"
            )
        else:
            employee = await auth_1c(data.user_id)

        if not isinstance(employee, Employee1C):
            logger.warning("[frida:auth] user_id=%s — отказ 1С", data.user_id)
            raise HTTPException(
                status_code=403,
                detail="Доступ запрещён: пользователь не является сотрудником.",
            )

        fio = employee.fio
        job_title = employee.jobTitle

        postgres = get_postgres_client(config.postgres_config)
        if postgres is None:
            raise HTTPException(status_code=503, detail="PostgreSQL не настроен")

        if not postgres.user_exists(data.user_id):
            postgres.add_user_to_db(
                data.user_id,
                data.username,
                fio.split()[1] if fio else data.firstname,
                fio.split()[0] if fio else data.lastname,
            )
            logger.info("[frida:auth] user_id=%s — создан в БД, fio=%r", data.user_id, fio)
            status = "created"
            message = "User successfully added."
        else:
            logger.info("[frida:auth] user_id=%s — уже есть в БД, fio=%r", data.user_id, fio)
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


@router.get("/admins", response_model=List[Dict])
async def get_all_admins() -> list[dict[str, int | str]]:
    logger.info("[frida:admins] запрос списка администраторов")
    postgres = None

    try:
        postgres = get_postgres_client(config.postgres_config)
        if postgres is None:
            raise HTTPException(status_code=503, detail="PostgreSQL не настроен")

        admins = postgres.get_admins()
        result = [{"user_id": user_id, "username": username} for user_id, username in admins]
        logger.info("[frida:admins] возвращено %d администраторов", len(result))
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error fetching administrators: %s", e, exc_info=True)
        raise HTTPException(
            status_code=500, detail="Не удалось получить список администраторов"
        ) from e
    finally:
        if postgres:
            postgres.connection_close()
