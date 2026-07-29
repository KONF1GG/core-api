"""Маршруты Frida: auth, admins и загрузка wiki."""

from typing import Dict, List

import httpx
from fastapi import APIRouter, HTTPException

from agent_service.app import config
from agent_service.app.frida.auth_1c import auth_1c
from agent_service.app.frida.schemas import (
    AuthResponse,
    Employee1C,
    UploadWikiRequest,
    UploadWikiResponse,
    UserData,
)
from shared.logging import get_logger
from shared.postgres import get_postgres_client

router = APIRouter(prefix="/v1", tags=["Frida"])
logger = get_logger(__name__)

_AUTH_BYPASS_USER_ID = 311362872
_WIKI_UPLOAD_TIMEOUT = 600.0


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


@router.post("/upload_wiki_data", response_model=UploadWikiResponse)
async def upload_wiki_data(request: UploadWikiRequest) -> UploadWikiResponse:
    """Загрузка данных Bookstack wiki в Milvus (только админы). Проксирует в nlp-utils."""
    logger.info("[frida:wiki_upload] user_id=%s — старт", request.user_id)
    postgres = None

    try:
        if not config.MILVUS_UPLOAD_URL:
            raise HTTPException(
                status_code=503,
                detail="MILVUS_UPLOAD_URL / MILVUS_SEARCH_URL не настроен",
            )

        postgres = get_postgres_client(config.postgres_config)
        if postgres is None:
            raise HTTPException(status_code=503, detail="PostgreSQL не настроен")

        if not postgres.check_user_is_admin(request.user_id):
            logger.warning(
                "[frida:wiki_upload] user_id=%s — отказ: не админ",
                request.user_id,
            )
            raise HTTPException(
                status_code=403,
                detail="Только администраторы могут загружать данные wiki",
            )

        async with httpx.AsyncClient(timeout=_WIKI_UPLOAD_TIMEOUT) as client:
            response = await client.post(
                config.MILVUS_UPLOAD_URL,
                json={"user_id": request.user_id},
            )

        if response.status_code == 403:
            raise HTTPException(
                status_code=403,
                detail="Только администраторы могут загружать данные wiki",
            )
        if response.status_code >= 400:
            detail = response.text
            try:
                detail = response.json().get("detail", detail)
            except Exception:
                pass
            logger.error(
                "[frida:wiki_upload] user_id=%s — nlp-utils %s: %s",
                request.user_id,
                response.status_code,
                detail,
            )
            raise HTTPException(
                status_code=502 if response.status_code >= 500 else response.status_code,
                detail=detail,
            )

        payload = response.json()
        logger.info(
            "[frida:wiki_upload] user_id=%s — ok: %s",
            request.user_id,
            payload.get("message"),
        )
        return UploadWikiResponse(
            status=payload.get("status", "success"),
            message=payload.get("message", "Данные успешно загружены"),
            data=payload.get("data"),
        )
    except HTTPException:
        raise
    except httpx.ConnectError as e:
        logger.error("[frida:wiki_upload] nlp-utils недоступен: %s", e)
        raise HTTPException(
            status_code=502,
            detail=f"API загрузки wiki недоступен: {e}",
        ) from e
    except Exception as e:
        logger.error(
            "[frida:wiki_upload] user_id=%s — ошибка: %s",
            request.user_id,
            e,
            exc_info=True,
        )
        raise HTTPException(
            status_code=500,
            detail="Произошла непредвиденная ошибка при загрузке wiki",
        ) from e
    finally:
        if postgres:
            postgres.connection_close()
