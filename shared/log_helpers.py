"""Утилиты для читаемых структурированных логов в stdout."""

from __future__ import annotations

import json
from typing import Any

from shared.schemas import ToolCallRecord


def truncate(value: str, max_len: int = 300) -> str:
    text = value.replace("\n", "\\n")
    if len(text) <= max_len:
        return text
    return f"{text[:max_len]}… (+{len(text) - max_len} симв.)"


def fmt_json(data: Any, max_len: int = 500) -> str:
    try:
        text = json.dumps(data, ensure_ascii=False, default=str)
    except TypeError:
        text = str(data)
    return truncate(text, max_len)


def summarize_tool_result(service: str, tool_name: str, result: Any) -> str:
    if isinstance(result, dict) and result.get("error"):
        return f"error={result['error']!r}"

    if not isinstance(result, dict):
        return truncate(str(result), 200)

    if service == "milvus":
        hashes = result.get("hashs") or []
        ctx = result.get("combined_context") or ""
        warning = result.get("warning")
        parts = [
            f"hashes={len(hashes)}",
            f"hash_list={hashes[:5]}{'…' if len(hashes) > 5 else ''}",
            f"context_len={len(ctx)}",
        ]
        if warning:
            parts.append(f"warning={warning!r}")
        return ", ".join(parts)

    if service == "tariff":
        status = result.get("status")
        parts = [f"status={status!r}"] if status is not None else []
        for key in ("address", "territory_name", "territory_id", "message"):
            if key in result and result[key]:
                parts.append(f"{key}={result[key]!r}")
        tariffs = result.get("tariffs")
        if isinstance(tariffs, list):
            parts.append(f"tariffs_count={len(tariffs)}")
        return ", ".join(parts) or fmt_json(result, 200)

    if service == "switcher":
        parts: list[str] = []
        for key in ("switch_ip", "switch_name", "free_ports", "summary", "status"):
            if key in result and result[key]:
                parts.append(f"{key}={truncate(str(result[key]), 80)!r}")
        if parts:
            return ", ".join(parts)
        return fmt_json(result, 200)

    return fmt_json(result, 200)


def summarize_tool_calls(tool_calls: list[ToolCallRecord]) -> str:
    if not tool_calls:
        return "нет"
    parts: list[str] = []
    for i, call in enumerate(tool_calls, 1):
        status = "ok" if call.error is None else f"err={call.error!r}"
        parts.append(f"{i}) {call.name}({fmt_json(call.arguments, 120)}) → {status}")
    return " | ".join(parts)
