"""
Модуль для работы с базами данных MySQL и PostgreSQL.

Содержит классы для подключения к базам данных и выполнения CRUD операций
с централизованным логированием всех операций.
"""

from typing import List
import psycopg2
import mysql.connector

from logger_config import get_logger

logger = get_logger(__name__)


class MySQL:
    """Класс для работы с базой данных MySQL."""

    def __init__(self, host, port, user, password, database) -> None:
        """
        Инициализирует подключение к MySQL.

        Args:
            host: Хост сервера MySQL
            port: Порт сервера MySQL
            user: Имя пользователя
            password: Пароль
            database: Название базы данных
        """
        try:
            logger.info("Connecting to MySQL: %s:%s/%s", host, port, database)
            self.conn = mysql.connector.connect(
                host=host, port=port, user=user, password=password, database=database
            )
            self.cursor = self.conn.cursor()
            logger.debug("MySQL connection established successfully")
        except Exception as e:
            logger.error("Failed to connect to MySQL: %s", e)
            raise

    def connection_close(self):
        """Закрывает соединение с MySQL."""
        try:
            self.cursor.close()
            self.conn.close()
            logger.debug("MySQL connection closed")
        except Exception as e:
            logger.warning("Error closing MySQL connection: %s", e)

    def get_pages_data(self):
        """
        Получает данные страниц из базы данных.

        Returns:
            list: Список словарей с данными страниц
        """
        try:
            logger.debug("Fetching pages data from MySQL")
            self.cursor.execute("""
            SELECT DISTINCT p.name, p.text, b.slug, p.slug, c.name
            FROM pages p
            JOIN books b ON p.book_id = b.id
            LEFT JOIN chapters c ON p.chapter_id = c.id
            JOIN bookshelves_books bb ON bb.book_id = b.id
            WHERE bb.bookshelf_id NOT IN (1, 10) AND p.`text` <> ''
            """)
            rows = self.cursor.fetchall()

            if not rows:
                logger.warning("No pages data found")
                return []

            result = [
                {
                    "page_name": row[0],
                    "page_text": row[1],
                    "book_slug": row[2],
                    "page_slug": row[3],
                    "chapter_name": row[4],
                }
                for row in rows
            ]

            logger.info("Retrieved %d pages from MySQL", len(result))
            return result

        except Exception as e:
            logger.error("Error fetching pages data: %s", e)
            raise


class PostgreSQL:
    """Класс для работы с базой данных PostgreSQL."""

    def __init__(self, host, port, user, password, database) -> None:
        """
        Инициализирует подключение к PostgreSQL.

        Args:
            host: Хост сервера PostgreSQL
            port: Порт сервера PostgreSQL
            user: Имя пользователя
            password: Пароль
            database: Название базы данных
        """
        try:
            logger.info("Connecting to PostgreSQL: %s:%s/%s", host, port, database)
            self.connection = psycopg2.connect(
                host=host, port=port, user=user, password=password, database=database
            )
            self.cursor = self.connection.cursor()
            logger.debug("PostgreSQL connection established successfully")
        except Exception as e:
            logger.error("Failed to connect to PostgreSQL: %s", e)
            raise

    def insert_new_topic(self, topic_hash, title, text, user_id):
        """
        Вставляет новую тему в базу данных.

        Args:
            topic_hash: Хэш темы
            title: Заголовок темы
            text: Текст темы
            user_id: ID пользователя
        """
        try:
            logger.debug("Inserting new topic with hash: %s", topic_hash)

            query = """
                INSERT INTO frida_storage (hash, title, text, isexstra)
                VALUES (%s, %s, %s, %s)
            """
            self.cursor.execute(query, (topic_hash, title, text, True))

            exstra_query = """
                INSERT INTO exstraTopics (hash, user_id)
                VALUES (%s, %s)
            """
            self.cursor.execute(exstra_query, (topic_hash, user_id))
            self.connection.commit()

            logger.info("Successfully inserted new topic for user: %s", user_id)

        except Exception as e:
            logger.error("Error inserting new topic: %s", e)
            self.connection.rollback()
            raise

    def add_user_to_db(
        self, user_id: int, username: str, first_name: str, last_name: str
    ):
        """
        Добавляет нового пользователя в базу данных.

        Args:
            user_id: ID пользователя
            username: Имя пользователя
            first_name: Имя
            last_name: Фамилия
        """
        try:
            logger.debug("Adding new user: %s", user_id)
            query = """
                INSERT INTO users (user_id, username, first_name, last_name)
                VALUES (%s, %s, %s, %s)
            """
            self.cursor.execute(query, (user_id, username, first_name, last_name))
            self.connection.commit()
            logger.info("Successfully added user: %s", user_id)
        except Exception as e:
            logger.error("Error adding user %s: %s", user_id, e)
            self.connection.rollback()
            raise

    def log_message(
        self,
        user_id,
        user_query,
        response,
        response_status,
        topic_hashs: List[str],
        category: str = "",
    ):
        """
        Логирует сообщение пользователя.

        Args:
            user_id: ID пользователя
            user_query: Запрос пользователя
            response: Ответ системы
            response_status: Статус ответа
            topic_hashs: Список хэшей тем
            category: Категория запроса
        """
        try:
            logger.debug("Logging message for user: %s", user_id)
            query = """
                INSERT INTO bot_logs (user_id, query, response, response_status, category)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING log_id;
            """
            self.cursor.execute(
                query, (user_id, user_query, response, response_status, category)
            )
            result = self.cursor.fetchone()
            log_id = result[0] if result else None

            for topic_hash in topic_hashs:
                hash_query = """
                    INSERT INTO bot_log_topic_hashes (log_id, topic_hash)
                    VALUES (%s, %s)
                """
                self.cursor.execute(hash_query, (log_id, topic_hash))

            self.connection.commit()
            logger.info("Successfully logged message for user: %s", user_id)

        except Exception as e:
            logger.error("Error logging message for user %s: %s", user_id, e)
            self.connection.rollback()
            raise

    def user_exists(self, user_id: int):
        """Проверяет существование пользователя в базе данных."""
        try:
            query = "SELECT 1 FROM users WHERE user_id = %s"
            self.cursor.execute(query, (user_id,))
            result = self.cursor.fetchone()
            exists = result is not None
            logger.debug("User %s exists: %s", user_id, exists)
            return exists
        except Exception as e:
            logger.error("Error checking user existence %s: %s", user_id, e)
            raise

    def check_user_is_admin(self, user_id):
        """Проверяет, является ли пользователь администратором."""
        try:
            query = "SELECT is_admin FROM users WHERE user_id = %s"
            self.cursor.execute(query, (user_id,))
            result = self.cursor.fetchone()
            is_admin = result[0] if result else None
            logger.debug("User %s is admin: %s", user_id, is_admin)
            return is_admin
        except Exception as e:
            logger.error("Error checking admin status for user %s: %s", user_id, e)
            raise

    def get_admins(self):
        """Получает список администраторов."""
        try:
            query = "SELECT user_id, username FROM users WHERE is_admin = TRUE;"
            self.cursor.execute(query)
            result = self.cursor.fetchall()
            logger.debug("Retrieved %d admin users", len(result))
            return result
        except Exception as e:
            logger.error("Error getting admin list: %s", e)
            raise

    def get_data_for_vector_db(self):
        """Получает данные для векторной базы."""
        try:
            query = "SELECT hash, book_name, title, text FROM frida_storage"
            self.cursor.execute(query)
            result = self.cursor.fetchall()
            logger.debug("Retrieved %d records for vector DB", len(result))
            return result
        except Exception as e:
            logger.error("Error getting vector DB data: %s", e)
            raise

    def get_history(self, user_id):
        """Получает историю сообщений пользователя."""
        try:
            query = """
            WITH LastThreeLogs AS (
                SELECT *
                FROM bot_logs bl
                WHERE bl.user_id = %s
                ORDER BY bl.created_at DESC
                LIMIT 3
            )
            SELECT *
            FROM LastThreeLogs
            ORDER BY created_at ASC;
            """
            self.cursor.execute(query, (user_id,))
            result = self.cursor.fetchall()
            logger.debug(
                "Retrieved %d history records for user %s", len(result), user_id
            )
            return result
        except Exception as e:
            logger.error("Error getting history for user %s: %s", user_id, e)
            raise

    def get_topics_texts_by_hashs(self, hashs: tuple[str]):
        """Получает тексты тем по их хэшам."""
        if not hashs:
            return []

        try:
            placeholders = ", ".join(["%s"] * len(hashs))
            query = f"""
                SELECT book_name, text, url
                FROM frida_storage fs
                WHERE fs.hash IN ({placeholders})
            """
            self.cursor.execute(query, hashs)
            result = self.cursor.fetchall()
            logger.debug("Retrieved %d topics for %d hashes", len(result), len(hashs))
            return result
        except Exception as e:
            logger.error("Error getting topics by hashes: %s", e)
            return []

    def delete_items_by_hashs(self, hashs):
        """Удаляет элементы из базы данных по хэшам."""
        try:
            hashs = tuple(hashs)
            query = "DELETE FROM frida_storage WHERE hash IN %s"
            self.cursor.execute(query, (hashs,))
            self.connection.commit()
            affected_rows = self.cursor.rowcount
            logger.info("Deleted %d items by hashes", affected_rows)
            return affected_rows
        except Exception as e:
            logger.error("Error deleting items by hashes: %s", e)
            self.connection.rollback()
            raise

    def get_count(self):
        """Получает количество записей в базе данных."""
        try:
            query = "SELECT COUNT(*) FROM frida_storage fs2"
            self.cursor.execute(query)
            result = self.cursor.fetchone()
            count = result[0] if result else None
            logger.debug("Total records count: %s", count)
            return count
        except Exception as e:
            logger.error("Error getting records count: %s", e)
            raise

    def connection_close(self):
        """Закрывает соединение с PostgreSQL."""
        try:
            self.cursor.close()
            self.connection.close()
            logger.debug("PostgreSQL connection closed")
        except Exception as e:
            logger.warning("Error closing PostgreSQL connection: %s", e)
