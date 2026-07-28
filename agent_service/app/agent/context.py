"""Хранение контекста диалога."""

import json

from agent_service.app import config
from shared.log_helpers import truncate
from shared.logging import get_logger
from shared.redis_adapter_client import (
    RedisAdapterClient,
    RedisAdapterError,
    get_redis_adapter_client,
)

logger = get_logger(__name__)


class ConversationContext:
    """Временная история текущей сессии в Redis (скользящее окно + TTL).

    Постоянная история хранится в PostgreSQL; Redis используется только
    как краткоживущий кэш контекста для LLM в рамках активной сессии.
    """

    def __init__(
        self,
        window_size: int | None = None,
        ttl_seconds: int | None = None,
    ):
        self.window_size = (
            window_size
            if window_size is not None
            else config.AGENT_HISTORY_WINDOW_SIZE
        )
        self.ttl_seconds = (
            ttl_seconds
            if ttl_seconds is not None
            else config.AGENT_HISTORY_TTL_SECONDS
        )

    def _client(self) -> RedisAdapterClient | None:
        if not config.REDIS_ADAPTER_URL:
            return None
        return get_redis_adapter_client(config.REDIS_ADAPTER_URL)

    async def load_history(self, session_id: str) -> str:
        client = self._client()
        if client is None:
            logger.info("[redis:history] session=%s — Redis не настроен, история пуста", session_id)
            return ""

        key = self._key(session_id)
        try:
            response = await client.raw_read(f"LRANGE {key} 0 {self.window_size - 1}")
            raw_items = client.unwrap_result(response)
        except RedisAdapterError as e:
            logger.warning("[redis:history] session=%s — ошибка загрузки: %s", session_id, e)
            return ""
        except Exception:
            logger.exception("[redis:history] session=%s — неожиданная ошибка", session_id)
            return ""

        if not isinstance(raw_items, list):
            logger.info("[redis:history] session=%s — пусто (нет записей)", session_id)
            return ""

        items = [json.loads(item) for item in reversed(raw_items)]
        history = "\n".join(
            f"{item['role']}: {item['content']}" for item in items if item.get("content")
        )
        logger.info(
            "[redis:history] session=%s — загружено %d ходов, %d симв., preview=%r",
            session_id,
            len(items),
            len(history),
            truncate(history, 100),
        )
        return history

    async def append_turn(self, session_id: str, user_message: str, answer: str) -> None:
        client = self._client()
        if client is None:
            logger.info("[redis:history] session=%s — Redis не настроен, ход не сохранён", session_id)
            return

        key = self._key(session_id)
        assistant = json.dumps(
            {"role": "assistant", "content": answer}, ensure_ascii=False
        )
        user = json.dumps(
            {"role": "user", "content": user_message}, ensure_ascii=False
        )
        commands = [
            f"LPUSH {key} {client.quote_arg(assistant)} {client.quote_arg(user)}",
            f"LTRIM {key} 0 {self.window_size - 1}",
            f"EXPIRE {key} {self.ttl_seconds}",
        ]
        try:
            await client.pipeline(commands)
            logger.info(
                "[redis:history] session=%s — сохранён ход (user=%d симв., answer=%d симв., ttl=%ds)",
                session_id,
                len(user_message),
                len(answer),
                self.ttl_seconds,
            )
        except RedisAdapterError as e:
            logger.warning("[redis:history] session=%s — ошибка сохранения: %s", session_id, e)
        except Exception:
            logger.exception("[redis:history] session=%s — неожиданная ошибка сохранения", session_id)

    @staticmethod
    def _key(session_id: str) -> str:
        return f"agent-service:history:{session_id}"
