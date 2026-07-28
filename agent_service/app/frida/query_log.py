"""Логирование chat-запросов в PostgreSQL."""

from shared.logging import get_logger
from shared.postgres import get_postgres_client
from shared.schemas import ChatRequest, ToolCallRecord

from agent_service.app import config

logger = get_logger(__name__)

_SOURCE_TYPE = {
    "telegram": "telegram",
    "web": "web",
    "max": "telegram",
    "api": "web",
}


def _topic_hashes(tool_calls: list[ToolCallRecord]) -> list[str]:
    hashes: list[str] = []
    for call in tool_calls:
        if not call.name.startswith("milvus."):
            continue
        result = call.result if isinstance(call.result, dict) else {}
        hashes.extend(result.get("hashs") or [])
    return list(dict.fromkeys(hashes))


def _category(tool_calls: list[ToolCallRecord]) -> str:
    for call in tool_calls:
        if call.name.startswith("tariff."):
            return "Тарифы"
        if call.name.startswith("switcher."):
            return "Коммутаторы"
    return "Общий"


def log_chat_request(
    request: ChatRequest,
    answer: str,
    success: bool,
    tool_calls: list[ToolCallRecord],
) -> None:
    pg_config = config.postgres_config
    if not pg_config:
        logger.debug("[pg:log] PostgreSQL не настроен — пропуск записи")
        return

    try:
        user_id = int(request.user_id)
    except ValueError:
        logger.warning(
            "[pg:log] user_id=%r не число — пропуск записи в query_logs",
            request.user_id,
        )
        return

    hashes = _topic_hashes(tool_calls)
    category = _category(tool_calls)
    postgres = None
    try:
        postgres = get_postgres_client(pg_config)
        if postgres is None:
            return
        postgres.log_message(
            user_id=user_id,
            user_query=request.message,
            response=answer,
            response_status=success,
            topic_hashes=hashes,
            category=category,
            source_type=_SOURCE_TYPE.get(request.source, request.source),
        )
        logger.info(
            "[pg:log] user_id=%s session=%s ok=%s category=%r source=%s "
            "hashes=%d answer_len=%d query=%r",
            request.user_id,
            request.session_id,
            success,
            category,
            _SOURCE_TYPE.get(request.source, request.source),
            len(hashes),
            len(answer),
            request.message[:100],
        )
    except Exception as e:
        logger.error(
            "[pg:log] user_id=%s session=%s — ошибка записи: %s",
            request.user_id,
            request.session_id,
            e,
            exc_info=True,
        )
    finally:
        if postgres:
            postgres.connection_close()
