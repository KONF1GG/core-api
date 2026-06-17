"""
Модуль конфигурации приложения.

Загружает переменные окружения для подключения к сервисам:
Redis, MySQL, PostgreSQL и API ключи для AI сервисов.
"""

import os
from dotenv import load_dotenv
from logger_config import get_logger

# Загрузка переменных окружения из .env
load_dotenv()

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

# Внешние сервисы для тарифной логики
REDIS_ADAPTER_URL = os.getenv("REDIS_ADAPTER_URL")
LLM_URL = os.getenv("LLM_URL")

# AI Промты (загружаются из переменных окружения для ConfigMap)
PROMPT_VOICE = os.getenv(
    "PROMPT_VOICE",
    """Ты - бот-помощник компании Фридом. Твоя задача проанализировать вопрос и контекст звукового файла.
    Учитывай, что текст может содержать ошибки, поскольку был обработан из голосового сообщения.
    Если вопроса нет, отвечай согласно тексту голосового сообщения. Используй HTML теги где нужно что-то выделить.
    Делай текст хорошо структурированным и понятным. НЕ ИСПОЛЬЗУЙ MARKDOWN.
    Только эти теги HTML (<b>, <i>, <a>, <code>, <pre>) НЕЛЬЗЯ ИСПОЛЬЗОВАТЬ: <ul>, <br>, <table>, <small> и остальные!
    Отвечай четко и кратко на вопрос и только на русском."""
)

PROMPT_CSV = os.getenv(
    "PROMPT_CSV",
    """Ты бот-помощник компании Фридом. Обработай файл таблицы по запросу.
    Если нет вопроса, то просто опиши таблицу. Используй HTML теги где нужно что-то выделить.
    Делай текст хорошо структурированным и понятным. НЕ ИСПОЛЬЗУЙ MARKDOWN.
    Только эти теги HTML (<b>, <i>, <a>, <code>, <pre>) НЕЛЬЗЯ ИСПОЛЬЗОВАТЬ: <ul>, <br>, <table>, <small> и остальные!
    Отвечай четко и кратко на вопрос и только на русском."""
)

PROMPT_TEXT = os.getenv(
    "PROMPT_TEXT",
    """Ты бот-помощник компании Фридом. Твоя задача — отвечать на вопросы сотрудников компании,
    основываясь на предоставленных данных из корпоративной WIKI, содержащих важную информацию из статей.

    Инструкции:
    1. Если вопрос не про тарифы, то отвечай на него как обычно.
    2. Если вопрос о тарифах:
       - Если в контексте представлен контекст тарифов, то есть словарь с тарифами, ответь на вопрос как обычно.
       - Если в контексте текст со ссылками на WIKI, это значит, что человек не указал территорию через команду /tariff. Предложи воспользоваться этой командой, чтобы уточнить территорию, а затем задать вопрос.
    3. Не выдумывай факты, используй только предоставленные данные, которые точно отвечают на поставленный вопрос. Если нет информации в представленных контекстах WIKI то ты должна сказать, чтобы переформулировали вопрос поскольку в найденных данных нет ответа на вопрос
    4. Строго запрещено использовать MARKDOWN. Используй только эти теги HTML (<b>, <i>, <a>, <code>, <pre>) НЕЛЬЗЯ ИСПОЛЬЗОВАТЬ: <ul>, <br>, <table>, <small> и остальные!
    5. Если в контексте указана ссылка начинающиеся на http://wiki.freedom1.ru:8080/ , то прикрепи откуда брал информацию в ответе. В вопросе про тарифы это не нужно."""
)

PROMPT_CLASSIFICATION = os.getenv(
    "PROMPT_CLASSIFICATION",
    """Определи категорию следующего запроса пользователя и извлеки адрес, если он есть.

    Категория "Тарифы" — только если в запросе есть слово "тариф" (как отдельное слово или часть составного слова, например, "тарифы", "тарифном") или точная фраза "стоимость подключения".
    Категория "Коммутаторы" - только вопросы о свободных портах на коммутаторе.
    Категория "Общий" — все остальное, включая стоимость доп. услуг (Статический IP, Видеонаблюдение, Домофония, Рассрочка, Аренда оборудования).
  
    Доступные категории: {categories}.

    Запрос: "{user_query}"

    Верни ответ в следующем формате:
    Категория: [название категории]
    Адрес: [извлеченный адрес или "не найден"]

    Если в запросе есть упоминание адреса (улица, дом, населенный пункт, регион, сокращения: ул., д., г., обл., р-н, снт, кв., корп., стр., мкр., пр., ш., пер., пл.), обязательно извлеки его целиком как строку."""
)

PROMPT_DEFAULT = os.getenv(
    "PROMPT_DEFAULT",
    "Ты — бот-помощник. Отвечай четко и кратко на русском языке."
)

# Конфигурация для анализа коммутаторов
ZABBIX_URL = os.getenv("ZABBIX_URL", "http://localhost/zabbix")
ZABBIX_USER = os.getenv("ZABBIX_USER", "Admin")
ZABBIX_PASSWORD = os.getenv("ZABBIX_PASSWORD", "zabbix")

CLICKHOUSE_HOST = os.getenv("CLICKHOUSE_HOST", "localhost")
CLICKHOUSE_PORT = os.getenv("CLICKHOUSE_PORT", "8123")
CLICKHOUSE_USER = os.getenv("CLICKHOUSE_USER", "default")
CLICKHOUSE_PASSWORD = os.getenv("CLICKHOUSE_PASSWORD", "")
CLICKHOUSE_DB = os.getenv("CLICKHOUSE_DB", "default")

SNMP_COMMUNITY = os.getenv("SNMP_COMMUNITY", "public")

# Промт для анализа коммутаторов
PROMPT_SWITCHER = os.getenv(
    "PROMPT_SWITCHER",
    """Ты — сетевой автоматизатор. Рассчитай свободные порты на коммутаторе.

ДАННЫЕ ДЛЯ АНАЛИЗА:
{context}

ПРАВИЛА:
1. FDB (ClickHouse) — главный источник занятости: порт в FDB = ЗАНЯТ.
2. Номера портов: сопоставляй FDB с SNMP ifDescr (извлекай число из имён вроде «Port 5», «GigabitEthernet0/0/5»).
3. Всего портов: expected_ports из Zabbix; если 0 или модель Unknown — считай физические Ethernet-порты по SNMP (исключи Loopback, VLAN, Management).
4. Uplink/trunk-порты (последний порт, имена с uplink/trunk/25/26/27/28 на 28-портовых) — не включай в свободные.
5. SNMP up без записи в FDB — помечай отдельно как «возможно занят (MAC не виден)», не считай свободным.
6. Свободные = (1..N) минус занятые по FDB минус uplink минус «возможно занят». Группируй в диапазоны (2-7, 9-25).
7. Если источник недоступен — укажи это в отчёте и работай с оставшимися данными.

Формат ответа:
📊 Отчет по коммутатору: [Имя] ([IP])
• Модель: [Модель]
• Всего портов: [N]
• Занято по FDB: [порты или «нет данных»]
• SNMP up без FDB: [порты или «нет»]
• Статус источников: Zabbix [ok/нет] | FDB [ok/нет] | SNMP [ok/нет]
• ✅ Свободно: [диапазоны] ([количество] портов)

Отвечай кратко на русском.

Запрос пользователя: {query}"""
)


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
