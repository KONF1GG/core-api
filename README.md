# Core API

API сервис для работы с Redis, Telegram ботом Фридой и AI запросами.

## Описание

Core API предоставляет централизованный интерфейс для:
- Работы с Redis базой данных
- Интеграции с Telegram ботом Frida
- Обработки AI запросов
- Логирования и аутентификации

## Технологии

- **FastAPI** - веб-фреймворк для создания API
- **Redis** - база данных для кеширования
- **MySQL/PostgreSQL** - реляционные базы данных
- **OpenAI/Mistral AI** - интеграция с AI сервисами
- **Docker** - контейнеризация

## Установка

### Через Docker (рекомендуется)

```bash
# Клонируйте репозиторий
git clone <repository-url>
cd core-api

# Запустите через Docker Compose
docker-compose up -d
```

### Локальная установка

```bash
# Установите зависимости (требуется Python 3.13+)
pip install -e .

# Или с использованием uv
uv sync
```

## Настройка

Создайте файл `.env` с необходимыми переменными окружения:

```env
LOG_LEVEL=INFO
REDIS_URL=redis://localhost:6379
DATABASE_URL=your_database_url
OPENAI_API_KEY=your_openai_key
MISTRAL_API_KEY=your_mistral_key
```

## Запуск

### Docker
```bash
docker-compose up
```

### Локально
```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

API будет доступен по адресу: `http://localhost:8000`

## API Документация

После запуска сервиса документация доступна по адресам:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## Структура проекта

```
├── main.py              # Основное приложение FastAPI
├── config.py            # Конфигурация
├── dependencies.py      # Зависимости FastAPI
├── databases.py         # Подключения к БД
├── ai.py               # AI интеграции
├── funcs.py            # Вспомогательные функции
├── logger_config.py    # Настройка логирования
├── routes/             # API маршруты
│   ├── ai_router/      # AI запросы
│   ├── frida_routes/   # Telegram бот Frida
│   └── redis_routes/   # Redis операции
├── docker-compose.yml  # Docker конфигурация
└── pyproject.toml      # Зависимости проекта
```

## Разработка

Для разработки рекомендуется использовать виртуальное окружение:

```bash
# Создайте виртуальное окружение
python -m venv venv
source venv/bin/activate  # На Windows: venv\Scripts\activate

# Установите зависимости
pip install -e .

# Запустите в режиме разработки
uvicorn main:app --reload
```
