"""Проверка сотрудника через 1С."""

from typing import Dict

from aiohttp import ClientSession

from agent_service.app import config
from agent_service.app.frida.schemas import Employee1C
from shared.logging import get_logger

logger = get_logger(__name__)


async def auth_1c(telegram_id: int) -> Employee1C | Dict[str, str]:
    url = f"{config.AUTH_1C_URL}?query=emploeyy&telegramId={telegram_id}"
    logger.info("[frida:1c] → GET telegram_id=%s url=%s", telegram_id, config.AUTH_1C_URL)

    try:
        async with ClientSession() as session:
            async with session.get(url) as res:
                if res.status != 200:
                    logger.warning(
                        "[frida:1c] ← telegram_id=%s HTTP %s",
                        telegram_id,
                        res.status,
                    )
                    return {"error": "Ошибка соединения с 1С"}

                data = await res.json(content_type=None)
                if not data:
                    logger.info("[frida:1c] ← telegram_id=%s — не найден в 1С", telegram_id)
                    return {"error": "Доступ запрещён"}

                fio = data.get("fio")
                job_title = data.get("jobTitle")
                if fio and job_title:
                    logger.info(
                        "[frida:1c] ← telegram_id=%s ok fio=%r jobTitle=%r",
                        telegram_id,
                        fio,
                        job_title,
                    )
                    return Employee1C(fio=fio, jobTitle=job_title)

                logger.warning("[frida:1c] ← telegram_id=%s — неполный ответ: %s", telegram_id, data)
                return {"error": "Неизвестный ответ от 1С"}
    except Exception as e:
        logger.error("[frida:1c] ← telegram_id=%s ошибка: %s", telegram_id, e, exc_info=True)
        return {"error": "Ошибка соединения с 1С"}
