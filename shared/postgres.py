"""PostgreSQL-клиент для пользователей и логов запросов."""

from __future__ import annotations

from typing import Any

import psycopg2

from shared.logging import get_logger

logger = get_logger(__name__)


class PostgreSQL:
    def __init__(self, host: str, port: str | int, user: str, password: str, database: str) -> None:
        try:
            logger.info("Connecting to PostgreSQL: %s:%s/%s", host, port, database)
            self.connection = psycopg2.connect(
                host=host, port=port, user=user, password=password, database=database
            )
            self.cursor = self.connection.cursor()
        except Exception as e:
            logger.error("Failed to connect to PostgreSQL: %s", e)
            raise

    def add_user_to_db(
        self, user_id: int, username: str, first_name: str, last_name: str
    ) -> None:
        query = """
            INSERT INTO users (user_id, username, first_name, last_name)
            VALUES (%s, %s, %s, %s)
        """
        self.cursor.execute(query, (user_id, username, first_name, last_name))
        self.connection.commit()

    def user_exists(self, user_id: int) -> bool:
        self.cursor.execute("SELECT 1 FROM users WHERE user_id = %s", (user_id,))
        return self.cursor.fetchone() is not None

    def get_admins(self) -> list[tuple[int, str]]:
        self.cursor.execute("SELECT user_id, username FROM users WHERE is_admin = TRUE")
        return self.cursor.fetchall()

    def log_message(
        self,
        user_id: int,
        user_query: str,
        response: str,
        response_status: bool,
        topic_hashes: list[str],
        category: str = "",
        source_type: str = "web",
    ) -> None:
        self.cursor.execute(
            """
            INSERT INTO query_logs (user_id, query, response, response_status, category, source_type)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING log_id
            """,
            (user_id, user_query, response, response_status, category, source_type),
        )
        row = self.cursor.fetchone()
        log_id = row[0] if row else None

        for topic_hash in topic_hashes:
            self.cursor.execute(
                "INSERT INTO query_topic_hashes (log_id, topic_hash) VALUES (%s, %s)",
                (log_id, topic_hash),
            )

        self.connection.commit()

    def connection_close(self) -> None:
        try:
            self.cursor.close()
            self.connection.close()
        except Exception as e:
            logger.warning("Error closing PostgreSQL connection: %s", e)


def get_postgres_client(config: dict[str, Any] | None) -> PostgreSQL | None:
    if not config:
        return None
    return PostgreSQL(**config)
