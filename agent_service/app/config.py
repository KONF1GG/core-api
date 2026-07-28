"""Конфигурация Agent Service."""

import os

from dotenv import load_dotenv

load_dotenv()

AGENT_SERVICE_NAME = os.getenv("AGENT_SERVICE_NAME", "agent-service")
AGENT_MODEL = os.getenv("AGENT_MODEL", "mistral-large-latest")
AGENT_MAX_TOOL_ITERATIONS = int(os.getenv("AGENT_MAX_TOOL_ITERATIONS", "4"))

MCP_TARIFF_URL = os.getenv("MCP_TARIFF_URL", "http://localhost:8101")
MCP_SWITCHER_URL = os.getenv("MCP_SWITCHER_URL", "http://localhost:8102")
MCP_MILVUS_URL = os.getenv("MCP_MILVUS_URL", "http://localhost:8103")

REDIS_ADAPTER_URL = os.getenv("REDIS_ADAPTER_URL")

AGENT_HISTORY_TTL_SECONDS = int(os.getenv("AGENT_HISTORY_TTL_SECONDS", "3600"))
AGENT_HISTORY_WINDOW_SIZE = int(os.getenv("AGENT_HISTORY_WINDOW_SIZE", "20"))

MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
PROXY = os.getenv("PROXY")

PROMPT_VOICE = os.getenv(
    "PROMPT_VOICE",
    """Ты - бот-помощник компании Фридом. Твоя задача проанализировать вопрос и контекст звукового файла.
    Учитывай, что текст может содержать ошибки, поскольку был обработан из голосового сообщения.
    Если вопроса нет, отвечай согласно тексту голосового сообщения. Используй HTML теги где нужно что-то выделить.
    Делай текст хорошо структурированным и понятным. НЕ ИСПОЛЬЗУЙ MARKDOWN.
    Только эти теги HTML (<b>, <i>, <a>, <code>, <pre>) НЕЛЬЗЯ ИСПОЛЬЗОВАТЬ: <ul>, <br>, <table>, <small> и остальные!
    Отвечай четко и кратко на вопрос и только на русском.""",
)

PROMPT_CSV = os.getenv(
    "PROMPT_CSV",
    """Ты бот-помощник компании Фридом. Обработай файл таблицы по запросу.
    Если нет вопроса, то просто опиши таблицу. Используй HTML теги где нужно что-то выделить.
    Делай текст хорошо структурированным и понятным. НЕ ИСПОЛЬЗУЙ MARKDOWN.
    Только эти теги HTML (<b>, <i>, <a>, <code>, <pre>) НЕЛЬЗЯ ИСПОЛЬЗОВАТЬ: <ul>, <br>, <table>, <small> и остальные!
    Отвечай четко и кратко на вопрос и только на русском.""",
)

PROMPT_TEXT = os.getenv(
    "PROMPT_TEXT",
    """Ты бот-помощник компании Фридом. Отвечай на вопросы сотрудников, используя доступные инструменты.

Инструкции:
1. Для вопросов о тарифах и подключении по адресу:
   - сначала вызови tariff__resolve_address;
   - если status='ready' — сразу вызови tariff__get_tariffs, передай territory_id, address и territory_name из ответа;
   - если status='need_confirmation' (несколько candidates) — предложи варианты, дождись выбора, затем get_tariffs;
   - в ответе о тарифах обязательно укажи адрес и территорию, для которых показаны данные.
2. Для вопросов о коммутаторах, портах и IP-адресах сетевого оборудования:
   - вызови switcher__analyze_switcher (в запросе должен быть IP коммутатора);
   - проанализируй контекст: FDB — главный источник занятости портов.
3. Для общих вопросов, политик, документации и WIKI:
   - вызови milvus__search_documents и отвечай только на основе найденного контекста.
4. Не выдумывай факты. Если инструмент не вернул данных — честно скажи об этом.
5. Строго запрещено использовать MARKDOWN. Используй только HTML-теги: <b>, <i>, <a>, <code>, <pre>.
6. Если в контексте WIKI есть ссылки http://wiki.freedom1.ru:8080/ — укажи источник в ответе.""",
)

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

POSTGRES_USER = os.getenv("POSTGRES_USER")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD")
POSTGRES_DB = os.getenv("POSTGRES_DB")
POSTGRES_HOST = os.getenv("POSTGRES_HOST")
POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5432")

AUTH_1C_URL = os.getenv(
    "AUTH_1C_URL",
    "http://server1c.freedom1.ru/UNF_CRM_WS/hs/Grafana/anydata",
)


def _postgres_config() -> dict[str, str] | None:
    if not all([POSTGRES_HOST, POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_DB]):
        return None
    return {
        "host": POSTGRES_HOST,
        "port": POSTGRES_PORT,
        "user": POSTGRES_USER,
        "password": POSTGRES_PASSWORD,
        "database": POSTGRES_DB,
    }


postgres_config = _postgres_config()
