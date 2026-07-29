"""Центральный исполнитель агента — полный ReAct-цикл через native tool calling.

Поток для каждого запроса в чат:
    1. Загрузить историю диалога через redis-adapter.
    2. Обнаружить все доступные инструменты MCP-сервисов (GET /tools).
    3. Запустить цикл агента:
          LLM решает, какой инструмент вызвать (если нужен)
          → вызов через MCPAggregator
          → результат возвращается в LLM
          → повтор до AGENT_MAX_TOOL_ITERATIONS
       Цикл завершается, когда LLM возвращает текстовый ответ (без tool calls).
    4. Сохранить новый ход user/assistant через redis-adapter.
    5. Вернуть ChatResponse клиенту.
"""

import time

from agent_service.app import config
from agent_service.app.agent.context import ConversationContext
from agent_service.app.frida.query_log import log_chat_request
from agent_service.app.llm.provider import run_agent_loop
from agent_service.app.mcp.aggregator import MCPAggregator
from shared.log_helpers import summarize_tool_calls, truncate
from shared.logging import get_logger
from shared.schemas import ChatRequest, ChatResponse, TestChatResponse, ToolCallRecord

logger = get_logger(__name__)


class AgentExecutor:
    def __init__(
        self,
        mcp: MCPAggregator | None = None,
        context: ConversationContext | None = None,
    ):
        self.mcp = mcp or MCPAggregator()
        self.context = context or ConversationContext()

    async def run_stateless(
        self,
        message: str,
        *,
        model: str | None = None,
        input_type: str = "text",
    ) -> TestChatResponse:
        """Один запрос → ответ без истории, redis и логирования в PG."""
        model = model or config.AGENT_MODEL
        tools = await self.mcp.list_tools_for_llm()
        answer, tool_calls = await run_agent_loop(
            user_message=message,
            history="",
            tools=tools,
            mcp=self.mcp,
            max_iterations=config.AGENT_MAX_TOOL_ITERATIONS,
            model=model,
            input_type=input_type,
        )
        return TestChatResponse(text=answer, tool_calls=tool_calls, model=model)

    async def run(self, request: ChatRequest) -> ChatResponse:
        started = time.monotonic()
        model = request.model or config.AGENT_MODEL

        logger.info(
            "[chat:start] user_id=%s session=%s source=%s input_type=%s model=%s message=%r",
            request.user_id,
            request.session_id,
            request.source,
            request.input_type,
            model,
            truncate(request.message, 200),
        )

        history = await self.context.load_history(request.session_id)
        answer = ""
        tool_calls: list[ToolCallRecord] = []
        success = False

        try:
            tools = await self.mcp.list_tools_for_llm()

            answer, tool_calls = await run_agent_loop(
                user_message=request.message,
                history=history,
                tools=tools,
                mcp=self.mcp,
                max_iterations=config.AGENT_MAX_TOOL_ITERATIONS,
                model=model,
                input_type=request.input_type,
            )

            await self.context.append_turn(
                request.session_id, request.message, answer
            )
            success = True

            duration_ms = int((time.monotonic() - started) * 1000)
            logger.info(
                "[chat:done] user_id=%s session=%s ok=true duration_ms=%d "
                "answer_len=%d tools_used=%d | %s",
                request.user_id,
                request.session_id,
                duration_ms,
                len(answer),
                len(tool_calls),
                summarize_tool_calls(tool_calls),
            )

            return ChatResponse(
                text=answer,
                session_id=request.session_id,
                source=request.source,
                tool_calls=tool_calls,
                model=model,
            )
        except Exception as exc:
            duration_ms = int((time.monotonic() - started) * 1000)
            logger.error(
                "[chat:fail] user_id=%s session=%s duration_ms=%d tools_before_error=%d error=%s",
                request.user_id,
                request.session_id,
                duration_ms,
                len(tool_calls),
                exc,
                exc_info=True,
            )
            raise
        finally:
            log_chat_request(request, answer, success, tool_calls)
