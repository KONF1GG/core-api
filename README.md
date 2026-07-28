# Agent Service

Единая точка входа для клиентов (Telegram, Max, Web) с MCP-архитектурой.

## Архитектура

```text
clients (telegram / max / web)
        │
        ▼
agent-service  POST /v1/chat
        │
        ├── mcp-tariff    (адреса, тарифы)
        ├── mcp-switcher  (коммутаторы, порты)
        └── mcp-milvus    (wiki / vector search)
```

`agent-service` агрегирует инструменты MCP-сервисов, запускает ReAct-цикл с LLM
и возвращает готовый ответ клиенту.

## Быстрый старт

```bash
cp .env.example .env
# заполните API-ключи и REDIS_ADAPTER_URL

docker compose up --build -d
```

Сервисы:
- Agent Service: `http://localhost:8000`
- MCP Tariff: `http://localhost:8101`
- MCP Switcher: `http://localhost:8102`
- MCP Milvus: `http://localhost:8103`

## API

### Chat

```http
POST /v1/chat
```

```json
{
  "user_id": "123",
  "session_id": "tg_123",
  "source": "telegram",
  "message": "Какие тарифы на Ленина 5?",
  "input_type": "text"
}
```

### Диагностика

- `GET /health` — состояние agent-service
- `GET /v1/tools` — список инструментов со всех MCP-сервисов
- `GET /v1/mcp/health` — health-check MCP-сервисов

Проверка:

```bash
curl http://localhost:8000/v1/tools
curl http://localhost:8000/v1/mcp/health
```

## Структура

```text
agent_service/                  # deployable: единый brain (POST /v1/chat)
  app/
    main.py                     # FastAPI entrypoint
    api.py                      # /v1/chat, /v1/tools, /v1/mcp/health
    config.py                   # Redis adapter, LLM keys, prompts, MCP URLs
    agent/
      context.py                # история диалога через redis-adapter
      executor.py               # ReAct loop orchestration
    llm/
      provider.py               # LLM + tool calling
    mcp/
      aggregator.py             # HTTP-клиент MCP-сервисов

mcp_servers/                    # deployable: доменные MCP-сервисы
  base.py                       # общие /health и /tools
  tariff/
    server.py                   # resolve_address, get_tariffs
    config.py
    services/                   # доменная логика tariff
      tariff_service.py
      address_client.py
  switcher/
    server.py                   # analyze_switcher
    config.py
    analyzer.py                 # Zabbix / ClickHouse / SNMP
    probe.py                    # CLI-диагностика источников
  milvus/
    server.py                   # search_documents
    config.py

shared/                         # общие контракты и инфраструктура
  schemas.py                    # ChatRequest / ChatResponse
  logging.py                    # централизованное логирование
  redis_adapter_client.py       # HTTP-клиент redis-adapter

scripts/
  switcher_probe.py             # CLI для диагностики switcher
```

## История диалога

Хранится в Redis по ключу `agent-service:history:{session_id}` через HTTP-адаптер.
Это временный кэш для текущей сессии: скользящее окно (`AGENT_HISTORY_WINDOW_SIZE`, по умолчанию 20 ходов)
и TTL (`AGENT_HISTORY_TTL_SECONDS`, по умолчанию 3600 с). Постоянная история — в PostgreSQL.
Параметр подключения — `REDIS_ADAPTER_URL` в `.env`.