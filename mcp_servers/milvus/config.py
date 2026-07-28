"""Конфигурация MCP Milvus."""

import os

from dotenv import load_dotenv

load_dotenv()

MILVUS_SEARCH_URL = os.getenv("MILVUS_SEARCH_URL", "").rstrip("/")
