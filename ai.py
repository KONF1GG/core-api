"""
Модуль для взаимодействия с AI сервисами.

Поддерживает работу с Mistral, OpenAI и DeepSeek API.
Включает автоматические повторные попытки и переключение между моделями.
"""

import asyncio
import logging
from typing import Any, Literal, Optional
from fastapi import HTTPException
from mistralai.client import Mistral
from openai import AsyncOpenAI
from openai.types.responses import Response as OpenAIChatCompletionResponse
import httpx
from tenacity import (
    retry,
    stop_after_attempt,
    wait_fixed,
    retry_if_exception_type,
    before_log,
)

from config import (
    MISTRAL_API_KEY,
    OPENAI_API_KEY,
    DEEPSEEK_API_KEY,
    PROXY,
    PROMPT_VOICE,
    PROMPT_CSV,
    PROMPT_TEXT,
    PROMPT_DEFAULT,
)
from logger_config import get_logger
from routes.ai_router.schmeas import CategoryRequest
from promts import get_classification_prompt

logger = get_logger(__name__)


# Декораторы для повторных попыток
@retry(
    stop=stop_after_attempt(3),
    wait=wait_fixed(2),
    retry=retry_if_exception_type((asyncio.TimeoutError, ConnectionError, ValueError)),
    before=before_log(logger, logging.INFO),
)
async def mistral_request(api_key: str, model_name: str, messages: list) -> Any:
    """
    Отправляет запрос в Mistral API с автоматическими повторными попытками.

    Args:
        api_key: API ключ для Mistral
        model_name: Название модели
        messages: Список сообщений для чата

    Returns:
        MistralChatCompletionResponse: Ответ от Mistral API

    Raises:
        asyncio.TimeoutError: При превышении времени ожидания
        ConnectionError: При ошибках подключения
        ValueError: При неверных параметрах
    """
    logger.debug("Sending request to Mistral API with model: %s", model_name)
    async with Mistral(api_key=api_key) as client:
        return await client.chat.complete_async(model=model_name, messages=messages)


@retry(
    stop=stop_after_attempt(3),
    wait=wait_fixed(2),
    retry=retry_if_exception_type((asyncio.TimeoutError, ConnectionError, ValueError)),
    before=before_log(logger, logging.INFO),
)
async def openai_response_request(
    api_key: str, model_name: str, input_text: str
) -> OpenAIChatCompletionResponse:
    """
    Отправляет запрос в OpenAI Responses API с автоматическими повторными попытками.

    Args:
        api_key: API ключ для OpenAI
        model_name: Название модели
        input_text: Входной текст для обработки

    Returns:
        OpenAIChatCompletionResponse: Ответ от OpenAI API

    Raises:
        asyncio.TimeoutError: При превышении времени ожидания
        ConnectionError: При ошибках подключения
        ValueError: При неверных параметрах
    """
    logger.debug("Sending request to OpenAI API with model: %s", model_name)

    http_client = None
    if PROXY:
        logger.debug("Using proxy: %s", PROXY)
        http_client = httpx.AsyncClient(proxy=PROXY)

    client = AsyncOpenAI(api_key=api_key, http_client=http_client)

    try:
        return await client.responses.create(model=model_name, input=input_text)
    finally:
        if http_client:
            await http_client.aclose()


@retry(
    stop=stop_after_attempt(3),
    wait=wait_fixed(2),
    retry=retry_if_exception_type((asyncio.TimeoutError, ConnectionError, ValueError)),
    before=before_log(logger, logging.INFO),
)
async def deepseek_request(api_key: str, model_name: str, messages: list):
    """
    Отправляет запрос в DeepSeek API через OpenRouter с автоматическими повторными попытками.

    Args:
        api_key: API ключ для DeepSeek
        model_name: Название модели
        messages: Список сообщений для чата

    Returns:
        Ответ от DeepSeek API

    Raises:
        asyncio.TimeoutError: При превышении времени ожидания
        ConnectionError: При ошибках подключения
        ValueError: При неверных параметрах
    """
    logger.debug("Sending request to DeepSeek API with model: %s", model_name)

    client = AsyncOpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=api_key,
    )

    return await client.chat.completions.create(
        extra_body={}, model=model_name, messages=messages
    )


# Словарь для конфигурации моделей
MODEL_CONFIG = {
    "mistral-large-latest": {
        "api_key": MISTRAL_API_KEY,
        "handler": mistral_request,
        "response_field": lambda r: r.choices[0].message.content,
    },
    "gpt-4o-mini": {
        "api_key": OPENAI_API_KEY,
        "handler": openai_response_request,
        "response_field": lambda r: r.output_text,
    },
    "deepseek/deepseek-chat-v3-0324:free": {
        "api_key": DEEPSEEK_API_KEY,
        "handler": deepseek_request,
        "response_field": lambda r: r.choices[0].message.content,
    },
}

# Порядок попыток моделей по умолчанию
DEFAULT_MODEL_ORDER = [
    "mistral-large-latest",
    "deepseek/deepseek-chat-v3-0324:free",
    "gpt-4o-mini",
]

# Словарь промптов по типу ввода (загружается из config)
PROMPT_TEMPLATES = {
    "voice": PROMPT_VOICE,
    "csv": PROMPT_CSV,
    "text": PROMPT_TEXT,
}


async def try_model(
    model: str,
    api_key: str,
    handler,
    get_response_text,
    input_type: str,
    query: str,
    context: str,
    history: str,
) -> str:
    """
    Отправляет запрос к конкретной AI модели.

    Args:
        model: Название модели
        api_key: API ключ
        handler: Функция-обработчик для отправки запроса
        get_response_text: Функция для извлечения текста из ответа
        input_type: Тип входных данных
        query: Запрос пользователя
        context: Контекст
        history: История диалога

    Returns:
        str: Ответ от модели
    """
    logger.debug("Trying model: %s", model)

    if handler == openai_response_request:
        prompt = f"{PROMPT_TEMPLATES.get(input_type, '')}\n\nЗапрос: {query}\nКонтекст: {context}\nИстория: {history}"
        response = await handler(api_key, model, prompt)
    else:
        system_content = PROMPT_TEMPLATES.get(input_type, PROMPT_DEFAULT)
        messages = [
            {"role": "system", "content": system_content},
            {
                "role": "user",
                "content": f"Запрос: {query}\nКонтекст: {context}\nИстория: {history}",
            },
        ]
        response = await handler(api_key, model, messages)

    result = get_response_text(response)
    logger.info("Successfully got response from model: %s", model)
    return result


async def get_ai(
    query: str,
    context: str = "",
    history: str = "",
    input_type: Literal["voice", "csv", "text"] = "text",
    model: Optional[str] = None,
) -> str:
    """
    Получает ответ от AI модели с автоматическим переключением между моделями.

    Args:
        query: Запрос пользователя
        context: Контекст для анализа (текст таблицы или расшифровка голосового сообщения)
        history: История диалога
        input_type: Тип ввода ('voice', 'csv', 'text')
        model: Название модели (если None, пробуем все доступные)

    Returns:
        str: Ответ модели

    Raises:
        HTTPException: При недоступности всех моделей или неподдерживаемой модели
    """
    logger.info(
        "Processing AI request: query_length=%d, input_type=%s, model=%s",
        len(query),
        input_type,
        model or "auto",
    )

    original_model = model
    models_to_try = []

    if model:
        # Если передана конкретная модель, сначала пробуем её, потом остальные
        if model not in MODEL_CONFIG:
            logger.error("Unsupported model requested: %s", model)
            raise HTTPException(
                status_code=400,
                detail={
                    "status": "error",
                    "message": f"Модель '{model}' не поддерживается",
                },
            )
        models_to_try = [model] + [m for m in DEFAULT_MODEL_ORDER if m != model]
    else:
        # Если модель не указана, пробуем все в порядке по умолчанию
        models_to_try = DEFAULT_MODEL_ORDER

    last_error = None

    for current_model in models_to_try:
        try:
            logger.debug("Trying model: %s", current_model)
            model_config = MODEL_CONFIG[current_model]
            api_key = model_config["api_key"]
            handler = model_config["handler"]
            get_response_text = model_config["response_field"]

            response_text = await try_model(
                current_model,
                api_key,
                handler,
                get_response_text,
                input_type,
                query,
                context,
                history,
            )

            # Если это не первоначально запрашиваемая модель и была указана конкретная модель
            if original_model and current_model != original_model:
                logger.warning(
                    "Fallback to model %s from %s", current_model, original_model
                )
                return f"<i>⚠️ Используется модель {current_model}, так как {original_model} недоступна</i>\n\n{response_text}"

            logger.info("Successfully processed request with model: %s", current_model)
            return response_text

        except Exception as e:
            last_error = e
            logger.warning("Model %s failed: %s", current_model, str(e))
            continue

    # Если все модели не сработали
    logger.error("All models failed. Last error: %s", last_error)
    raise HTTPException(
        status_code=500,
        detail={
            "status": "error",
            "message": "Не удалось получить ответ ни от одной модели",
            "error": str(last_error),
        },
    )


async def classify_query(
    request_data: CategoryRequest
) -> dict:
    """
    Классифицирует запрос пользователя с помощью AI.

    Args:
        request_data: Данные запроса с текстом для классификации

    Returns:
        dict: Результат классификации с полями:
            - category: Категория запроса (Тарифы, Общий, Коммутаторы)
            - address: Извлеченный адрес или None
            - raw_response: Полный ответ от AI
    """
    try:
        categories = ["Тарифы", "Общий", "Коммутаторы"]

        # Формируем промт для классификации
        classification_prompt = get_classification_prompt(categories, request_data.query)

        # Классифицируем запрос через AI
        logger.debug("Отправляем запрос на классификацию к AI модели...")
        classification_result = await get_ai(
            query=classification_prompt,
            context="",
            history="",
            input_type="text",
            model="mistral-large-latest",
        )

        logger.debug(f"Результат классификации: {classification_result}")

        if not classification_result:
            logger.error("Не удалось классифицировать запрос")
            return {
                "category": "Общий",
                "address": None,
                "raw_response": None
            }

        # Определяем категорию и извлекаем адрес
        logger.debug("Начинаем разбор результата классификации...")
        category = None
        extracted_address = None
        classification_lower = classification_result.lower().strip()
        logger.debug(f"Результат для анализа: {classification_lower}")

        # Парсим категорию
        if "тариф" in classification_lower:
            category = "Тарифы"
            logger.debug("Определена категория: Тарифы")
        elif "коммутатор" in classification_lower:
            category = "Коммутаторы"
            logger.debug("Определена категория: Коммутаторы")
        else:
            category = "Общий"
            logger.debug("Категория не определена, используем: Общий")

        # Парсим адрес из ответа LLM
        logger.debug("Ищем адрес в ответе...")
        lines = classification_result.split("\n")
        for line in lines:
            if "адрес:" in line.lower():
                address_part = line.split(":", 1)[1].strip()
                if address_part and address_part.lower() != "не найден":
                    extracted_address = address_part
                    logger.debug(f"Найден адрес: {extracted_address}")
                break

        if not extracted_address:
            logger.debug("Адрес не найден в ответе")

        logger.info(
            f"Запрос классифицирован как: {category}, извлеченный адрес: {extracted_address}"
        )

        return {
            "category": category,
            "address": extracted_address,
            "raw_response": classification_result
        }

    except Exception as e:
        logger.exception(f"Ошибка при классификации запроса: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "status": "error",
                "message": "Ошибка при классификации запроса",
                "error": str(e),
            },
        )
