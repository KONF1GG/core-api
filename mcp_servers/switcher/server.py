"""MCP-сервис коммутаторов — анализ сетевого оборудования через Zabbix, ClickHouse и SNMP."""

from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel

from mcp_servers.base import register_health_route, register_tools_route
from mcp_servers.switcher.analyzer import analyze_switch

SERVICE_NAME = "mcp-switcher"

TOOLS = [
    {
        "name": "analyze_switcher",
        "description": (
            "Анализирует сетевой коммутатор: занятость портов, количество свободных портов, "
            "таблица FDB, статусы портов по SNMP и данные из Zabbix. "
            "В запросе ОБЯЗАТЕЛЬНО должен быть IP-адрес коммутатора. "
            "Используй, когда пользователь спрашивает о портах, свободных портах, "
            "загрузке коммутатора или любом вопросе по конкретному IP коммутатора."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": (
                        "Запрос пользователя с IP-адресом коммутатора, "
                        "например 'сколько свободных портов на 10.0.1.5'"
                    ),
                }
            },
            "required": ["query"],
        },
    }
]

app = FastAPI(
    title="MCP Switcher",
    description="Доменные инструменты для анализа сетевых коммутаторов.",
    version="0.2.0",
)

register_health_route(app, SERVICE_NAME)
register_tools_route(app, TOOLS)


class AnalyzeSwitcherRequest(BaseModel):
    query: str


@app.post("/tools/analyze_switcher")
async def analyze_switcher(request: AnalyzeSwitcherRequest) -> dict[str, Any]:
    context = await analyze_switch(request.query)
    return {"context": context}
