"""Конфигурация MCP Tariff."""

import os

from dotenv import load_dotenv

load_dotenv()

REDIS_ADAPTER_URL = os.getenv("REDIS_ADAPTER_URL")
LLM_URL = os.getenv("LLM_URL")
