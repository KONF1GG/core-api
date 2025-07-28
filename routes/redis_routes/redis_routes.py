"""
Redis Routes - Маршруты для работы с Redis.

Содержит маршруты для экспорта пользователей, поиска адресов и получения тарифов.
Все операции выполняются асинхронно с подробным логированием.
"""

import json
import os
from pathlib import Path
import uuid
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from dependencies import RedisDependency
from funcs import cleanup_temp_dir
from logger_config import get_logger
from .redis_schemas import RedisAddressModel, RedisAddressModelResponse
from . import crud

router = APIRouter()
logger = get_logger(__name__)


@router.get("/all_users_from_redis", response_class=FileResponse, tags=["Redis"])
async def get_all_users_data_from_redis(redis: RedisDependency):
    """
    Экспортирует все данные пользователей из Redis в JSON файл.

    Args:
        redis: Подключение к Redis

    Returns:
        FileResponse: JSON файл с данными пользователей

    Raises:
        HTTPException: При ошибках обработки данных или создания файла
    """
    logger.info("Starting user data export from Redis")
    temp_dir = Path("temp_files")
    temp_dir.mkdir(exist_ok=True)
    cleanup_temp_dir(temp_dir)

    temp_filename = None

    try:
        logger.debug("Retrieving unique keys from Redis")
        unique_keys = list(await crud.get_unique_keys_with_prefix(redis=redis))
        logger.info("Found %d unique keys", len(unique_keys))

        result = []
        batch_size = 1024

        for i in range(0, len(unique_keys), batch_size):
            batch_keys = unique_keys[i : i + batch_size]
            logger.debug("Processing batch %d-%d", i, i + len(batch_keys))

            values = await redis.json().mget(batch_keys, path="$")
            cleaned_batch = []

            for item in values:
                if item and isinstance(item, list) and len(item) > 0:
                    cleaned_batch.append(item[0])

            result.extend(cleaned_batch)

        temp_filename = str(temp_dir / f"temp_users_{uuid.uuid4().hex}.json")
        logger.debug("Creating temporary file: %s", temp_filename)

        with open(temp_filename, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=4, ensure_ascii=False)

        if not os.path.exists(temp_filename):
            logger.error("Failed to create temporary file")
            raise HTTPException(500, detail="Failed to create temporary file")

        logger.info("Successfully exported %d user records", len(result))
        return FileResponse(
            path=temp_filename,
            media_type="application/json",
            filename="users_data.json",
        )

    except Exception as e:
        logger.error("Error during user data export: %s", e)
        if temp_filename and os.path.exists(temp_filename):
            os.remove(temp_filename)
        raise HTTPException(500, detail=str(e)) from e


@router.get(
    "/redis_addresses", tags=["Redis"], response_model=RedisAddressModelResponse
)
async def get_addresses(query_address: str, redis: RedisDependency):
    """
    Выполняет поиск адресов в Redis по запросу.

    Args:
        query_address: Строка для поиска адресов
        redis: Подключение к Redis

    Returns:
        RedisAddressModelResponse: Список найденных адресов

    Raises:
        HTTPException: При отсутствии результатов или ошибках поиска
    """
    logger.info("Searching addresses with query: %s", query_address)

    try:
        from redis.commands.search.query import Query

        query = Query(query_address.lower()).paging(0, 40)
        addresses = await redis.ft("idx:adds").search(query)

        if not addresses.docs:
            logger.warning("No addresses found for query: %s", query_address)
            raise HTTPException(status_code=404, detail="No addresses found")

        addresses_models = []
        for doc in addresses.docs:
            data = json.loads(doc.json)
            if data["territoryId"] is not None:
                addresses_models.append(
                    RedisAddressModel(
                        id=data["id"],
                        address=data.get("addressShort") or data.get("title", ""),
                        territory_id=data["territoryId"],
                        territory_name=data["territory"],
                        conn_type=data.get("conn_type"),
                    )
                )

        logger.info(
            "Found %d addresses for query: %s", len(addresses_models), query_address
        )
        return RedisAddressModelResponse(addresses=addresses_models)

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error searching addresses: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/redis_address_by_id", tags=["Redis"], response_model=RedisAddressModel)
async def get_address_by_id(address_id: str, redis: RedisDependency):
    """
    Получает конкретный адрес по ID из Redis.

    Args:
        address_id: Уникальный идентификатор адреса
        redis: Подключение к Redis

    Returns:
        RedisAddressModel: Данные адреса

    Raises:
        HTTPException: При отсутствии адреса или ошибках получения данных
    """
    logger.info("Retrieving address by ID: %s", address_id)

    try:
        address_result = await redis.json().get(f"adds:{address_id}")
        if address_result is None:
            logger.warning("Address not found for ID: %s", address_id)
            raise HTTPException(status_code=404, detail="Address not found")

        if isinstance(address_result, str):
            address_data = json.loads(address_result)
        else:
            address_data = address_result

        logger.debug("Successfully retrieved address for ID: %s", address_id)
        return RedisAddressModel(
            id=address_data["id"],
            address=address_data.get("addressShort") or address_data.get("title", ""),
            territory_id=address_data["territoryId"],
            territory_name=address_data["territory"],
            conn_type=address_data.get("conn_type"),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error retrieving address by ID %s: %s", address_id, e)
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/redis_tariffs", tags=["Redis"])
async def get_tariffs(territory_id: str, redis: RedisDependency):
    """
    Получает тарифы для указанной территории из Redis.

    Args:
        territory_id: Идентификатор территории
        redis: Подключение к Redis

    Returns:
        dict: Данные о тарифах для территории

    Raises:
        HTTPException: При отсутствии тарифов или ошибках получения данных
    """
    logger.info("Retrieving tariffs for territory: %s", territory_id)

    try:
        tariffs_result = await redis.json().get(f"terrtar:{territory_id}")
        if tariffs_result is None:
            logger.warning("No tariffs found for territory: %s", territory_id)
            raise HTTPException(status_code=404, detail="No tariffs found")

        if isinstance(tariffs_result, str):
            import json

            tariffs_result = json.loads(tariffs_result)

        logger.info("Successfully retrieved tariffs for territory: %s", territory_id)
        return tariffs_result

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error retrieving tariffs for territory %s: %s", territory_id, e)
        raise HTTPException(status_code=500, detail=str(e)) from e
