"""Точка входа Agent Service."""

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from agent_service.app import config
from agent_service.app.api import router as agent_router
from agent_service.app.frida.routes import router as frida_router
from shared.logging import setup_logging

log_level = os.getenv("LOG_LEVEL", config.LOG_LEVEL)
setup_logging(log_level)

app = FastAPI(
    title="Agent Service",
    description="Единый brain для клиентов Telegram, Max и Web через MCP-инструменты.",
    version="0.2.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(agent_router)
app.include_router(frida_router)


@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": config.AGENT_SERVICE_NAME}
