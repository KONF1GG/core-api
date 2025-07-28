"""
Модуль конфигурации приложения.

Загружает переменные окружения для подключения к сервисам:
Redis, MySQL, PostgreSQL и API ключи для AI сервисов.
"""

import os
from dotenv import dotenv_values
from logger_config import get_logger

# Загрузка переменных окружения
dotenv_values()

logger = get_logger(__name__)

# Redis конфигурация
REDIS_HOST = os.getenv("REDIS_HOST")
REDIS_PORT = os.getenv("REDIS_PORT")
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD")
REDIS_LOGIN = os.getenv("REDIS_LOGIN")

# MySQL конфигурация
HOST_MYSQL = os.getenv("HOST_MYSQL")
PORT_MYSQL = os.getenv("PORT_MYSQL")
USER_MYSQL = os.getenv("USER_MYSQL")
PASSWORD_MYSQL = os.getenv("PASSWORD_MYSQL")
DB_MYSQL = os.getenv("DB_MYSQL")

# PostgreSQL конфигурация
POSTGRES_USER = os.getenv("POSTGRES_USER")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD")
POSTGRES_DB = os.getenv("POSTGRES_DB")
POSTGRES_HOST = os.getenv("POSTGRES_HOST")
POSTGRES_PORT = os.getenv("POSTGRES_PORT")

# API ключи
MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")

# Прокси
PROXY = os.getenv("PROXY")


mysql_config = {
    "host": HOST_MYSQL,
    "port": PORT_MYSQL,
    "user": USER_MYSQL,
    "password": PASSWORD_MYSQL,
    "database": DB_MYSQL,
}


postgres_config = {
    "host": POSTGRES_HOST,
    "port": POSTGRES_PORT,
    "user": POSTGRES_USER,
    "password": POSTGRES_PASSWORD,
    "database": POSTGRES_DB,
}
