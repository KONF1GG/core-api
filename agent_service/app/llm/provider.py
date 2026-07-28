"""Фасад LLM для Agent Service — мультипровайдерный цикл агента.

Поддерживаемые провайдеры:
  • Mistral  (mistral-large-latest, mistral-small-latest, …)
  • OpenAI   (gpt-4o, gpt-4o-mini, …)
  • DeepSeek через OpenRouter (deepseek/deepseek-chat-v3-0324:free, …)

Все три используют один формат tool calling (OpenAI-compatible), поэтому
один цикл обрабатывает их все. Провайдер определяется по имени модели;
при ошибке выбранной модели выполняется fallback по FALLBACK_CHAIN.
"""

from __future__ import annotations

import json
import time
from typing import TYPE_CHECKING, Any

import httpx
from mistralai.client import Mistral
from openai import AsyncOpenAI

from agent_service.app import config
from agent_service.app.mcp.aggregator import parse_tool_name
from shared.log_helpers import fmt_json, summarize_tool_result, truncate
from shared.logging import get_logger
from shared.schemas import ToolCallRecord

if TYPE_CHECKING:
    from agent_service.app.mcp.aggregator import MCPAggregator

logger = get_logger(__name__)

# ─── реестр провайдеров ──────────────────────────────────────────────────────

# Префикс / точное имя модели → провайдер
_PROVIDER_MAP: dict[str, str] = {
    "mistral-large-latest":  "mistral",
    "mistral-small-latest":  "mistral",
    "mistral-medium-latest": "mistral",
    "open-mistral-7b":       "mistral",
    "open-mixtral-8x7b":     "mistral",
    "gpt-4o":                "openai",
    "gpt-4o-mini":           "openai",
    "gpt-4-turbo":           "openai",
    "gpt-3.5-turbo":         "openai",
    "o1":                    "openai",
    "o3":                    "openai",
    "deepseek/deepseek-chat-v3-0324:free": "deepseek",
    "deepseek/deepseek-r1:free":           "deepseek",
}

# При ошибке запрошенной модели пробуем эти варианты по порядку
FALLBACK_CHAIN: list[tuple[str, str]] = [
    ("mistral-large-latest",               "mistral"),
    ("deepseek/deepseek-chat-v3-0324:free","deepseek"),
    ("gpt-4o-mini",                        "openai"),
]


def detect_provider(model: str) -> str:
    """Определяет провайдера по имени модели; по умолчанию — Mistral."""
    if model in _PROVIDER_MAP:
        return _PROVIDER_MAP[model]
    low = model.lower()
    if low.startswith(("gpt-", "o1-", "o3-", "o4-")):
        return "openai"
    if "deepseek" in low:
        return "deepseek"
    return "mistral"


# ─── публичный API ───────────────────────────────────────────────────────────

async def run_agent_loop(
    *,
    user_message: str,
    history: str,
    tools: list[dict[str, Any]],
    mcp: MCPAggregator,
    max_iterations: int = 4,
    model: str = "mistral-large-latest",
    input_type: str = "text",
) -> tuple[str, list[ToolCallRecord]]:
    """
    ReAct-цикл агента — независимый от провайдера.

    1. Собрать начальные сообщения (системный промпт + история + сообщение пользователя).
    2. Сначала попробовать запрошенную модель; при ошибке — fallback по FALLBACK_CHAIN.
    3. На каждой итерации: отправить messages+tools → если LLM вернул tool_calls,
       выполнить их через MCPAggregator и добавить результаты; повторить.
    4. Когда LLM вернул текст (без tool_calls) → готово.
    5. Если исчерпан max_iterations → принудительный финальный ответ без tools.
    """
    messages = _build_messages(user_message=user_message, history=history, input_type=input_type)
    tool_call_records: list[ToolCallRecord] = []

    provider = detect_provider(model)
    chain = [(model, provider)] + [
        (m, p) for m, p in FALLBACK_CHAIN if m != model
    ]

    logger.info(
        "[llm:start] model=%s provider=%s input_type=%s tools=%d max_iter=%d history_len=%d message=%r",
        model,
        provider,
        input_type,
        len(tools),
        max_iterations,
        len(history),
        truncate(user_message, 200),
    )

    last_error: Exception | None = None
    for attempt_model, attempt_provider in chain:
        try:
            answer = await _run_loop(
                model=attempt_model,
                provider=attempt_provider,
                messages=messages,
                tools=tools,
                mcp=mcp,
                max_iterations=max_iterations,
                tool_call_records=tool_call_records,
            )
            if attempt_model != model:
                logger.warning(
                    "[llm:fallback] %s (%s) вместо %s (%s)",
                    attempt_model,
                    attempt_provider,
                    model,
                    provider,
                )
                answer = f"<i>⚠ Используется модель {attempt_model}</i>\n\n{answer}"
            logger.info(
                "[llm:done] model=%s provider=%s tool_calls=%d answer_len=%d",
                attempt_model,
                attempt_provider,
                len(tool_call_records),
                len(answer),
            )
            return answer, tool_call_records
        except Exception as exc:
            last_error = exc
            logger.warning(
                "[llm:error] model=%s provider=%s: %s",
                attempt_model,
                attempt_provider,
                exc,
            )
            # Сбрасываем записи, чтобы не дублировать при следующей попытке
            tool_call_records.clear()
            continue

    raise RuntimeError(f"Все модели недоступны. Последняя ошибка: {last_error}") from last_error


# ─── внутренние функции ──────────────────────────────────────────────────────

async def _run_loop(
    *,
    model: str,
    provider: str,
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]],
    mcp: MCPAggregator,
    max_iterations: int,
    tool_call_records: list[ToolCallRecord],
) -> str:
    """Запускает ReAct-цикл для одной пары (модель, провайдер)."""
    msgs = list(messages)

    for iteration in range(max_iterations):
        iter_no = iteration + 1
        logger.info(
            "[llm:iter] model=%s provider=%s iteration=%d/%d messages=%d",
            model,
            provider,
            iter_no,
            max_iterations,
            len(msgs),
        )
        llm_started = time.monotonic()

        response = await _chat_complete(
            model=model,
            provider=provider,
            messages=msgs,
            tools=tools,
        )
        llm_ms = int((time.monotonic() - llm_started) * 1000)

        msg = response.choices[0].message
        tool_calls = msg.tool_calls or []

        if not tool_calls:
            answer = _content(msg) or ""
            logger.info(
                "[llm:answer] model=%s iteration=%d llm_ms=%d answer_len=%d preview=%r",
                model,
                iter_no,
                llm_ms,
                len(answer),
                truncate(answer, 150),
            )
            return answer

        requested: list[str] = []
        for tc in tool_calls:
            try:
                args = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError:
                args = tc.function.arguments
            requested.append(f"{tc.function.name}({fmt_json(args, 120)})")
        logger.info(
            "[llm:tools_requested] model=%s iteration=%d llm_ms=%d count=%d tools=[%s]",
            model,
            iter_no,
            llm_ms,
            len(tool_calls),
            "; ".join(requested),
        )

        # Добавляем ход ассистента (с tool_calls) в диалог
        msgs.append(_assistant_dict(msg))

        # Выполняем каждый запрошенный инструмент
        for tc in tool_calls:
            fn_name = tc.function.name
            try:
                arguments: dict[str, Any] = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError:
                arguments = {}
                logger.warning(
                    "[llm:tool_args] не удалось распарсить JSON для %s: %r",
                    fn_name,
                    tc.function.arguments,
                )

            service, tool_name = _safe_parse(fn_name)
            record = ToolCallRecord(name=f"{service}.{tool_name}", arguments=arguments)
            tool_call_records.append(record)

            try:
                result = await mcp.call_tool(service, tool_name, arguments)
                record.result = result
                tool_result = json.dumps(result, ensure_ascii=False)
                logger.info(
                    "[llm:tool_ok] %s.%s args=%s → %s",
                    service,
                    tool_name,
                    fmt_json(arguments, 200),
                    summarize_tool_result(service, tool_name, result),
                )
            except Exception as exc:
                record.error = str(exc)
                tool_result = f"Ошибка инструмента {fn_name}: {exc}"
                logger.warning(
                    "[llm:tool_err] %s.%s args=%s error=%s",
                    service,
                    tool_name,
                    fmt_json(arguments, 200),
                    exc,
                )

            msgs.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "name": fn_name,
                "content": tool_result,
            })

    # Итерации исчерпаны — принудительный финальный ответ без tools
    logger.warning(
        "[llm:max_iter] model=%s достигнут лимит %d итераций, финальный ответ без tools",
        model,
        max_iterations,
    )
    final = await _chat_complete(model=model, provider=provider, messages=msgs, tools=[])
    return _content(final.choices[0].message) or ""


async def _chat_complete(
    *,
    model: str,
    provider: str,
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]],
) -> Any:
    """Вызывает нужный SDK в зависимости от провайдера."""
    kw: dict[str, Any] = {"model": model, "messages": messages}
    if tools:
        kw["tools"] = tools
        kw["tool_choice"] = "auto"

    if provider == "mistral":
        async with Mistral(api_key=config.MISTRAL_API_KEY) as client:
            return await client.chat.complete_async(**kw)

    # OpenAI-совместимый API (OpenAI и DeepSeek/OpenRouter)
    http_client = httpx.AsyncClient(proxy=config.PROXY) if config.PROXY else None
    if provider == "deepseek":
        openai_client = AsyncOpenAI(
            api_key=config.DEEPSEEK_API_KEY,
            base_url="https://openrouter.ai/api/v1",
            http_client=http_client,
        )
    else:
        openai_client = AsyncOpenAI(api_key=config.OPENAI_API_KEY, http_client=http_client)

    try:
        return await openai_client.chat.completions.create(**kw)
    finally:
        if http_client:
            await http_client.aclose()


def _build_messages(
    *,
    user_message: str,
    history: str,
    input_type: str,
) -> list[dict[str, Any]]:
    from agent_service.app import config  # noqa: PLC0415

    prompt_map = {
        "voice": config.PROMPT_VOICE,
        "csv": config.PROMPT_CSV,
        "text": config.PROMPT_TEXT,
    }
    system_content = prompt_map.get(input_type, config.PROMPT_TEXT)

    msgs: list[dict[str, Any]] = [{"role": "system", "content": system_content}]
    if history:
        msgs.append({"role": "user", "content": f"[История предыдущего диалога]\n{history}"})
        msgs.append({"role": "assistant", "content": "Принял, учту историю при ответе."})
    msgs.append({"role": "user", "content": user_message})
    return msgs


def _content(msg: Any) -> str:
    """Извлекает текстовое содержимое из объекта сообщения любого SDK."""
    c = msg.content
    if c is None:
        return ""
    if isinstance(c, str):
        return c
    # Mistral может вернуть список блоков контента
    if isinstance(c, list):
        return "".join(
            block.text if hasattr(block, "text") else str(block) for block in c
        )
    return str(c)


def _assistant_dict(msg: Any) -> dict[str, Any]:
    """Преобразует AssistantMessage любого SDK в обычный dict."""
    return {
        "role": "assistant",
        "content": _content(msg),
        "tool_calls": [
            {
                "id": tc.id,
                "type": "function",
                "function": {
                    "name": tc.function.name,
                    "arguments": tc.function.arguments,
                },
            }
            for tc in (msg.tool_calls or [])
        ],
    }


def _safe_parse(fn_name: str) -> tuple[str, str]:
    try:
        return parse_tool_name(fn_name)
    except ValueError:
        logger.error("Неизвестное имя функции инструмента: %r", fn_name)
        return "unknown", fn_name
