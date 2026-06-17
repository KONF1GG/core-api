#!/usr/bin/env python3
"""
CLI-обёртка для диагностики switcher.

Запуск из корня проекта:
    python scripts/switcher_probe.py 10.0.0.1
    python scripts/switcher_probe.py 10.0.0.1 --source zabbix
    python scripts/switcher_probe.py 10.0.0.1 --save /tmp/probe.json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from switcher import extract_ip_from_query  # noqa: E402
from switcher_probe import collect_switch_probe  # noqa: E402


def _print_section(title: str) -> None:
    line = "=" * 72
    print(f"\n{line}\n{title}\n{line}")


def _dump(label: str, data: Any, indent: int = 2) -> None:
    print(f"\n--- {label} ---")
    print(json.dumps(data, ensure_ascii=False, indent=indent, default=str))


def _print_probe(data: dict[str, Any]) -> None:
    print(f"Probe switch_ip={data.get('switch_ip')}")
    print(f"Config: {json.dumps(data.get('config', {}), ensure_ascii=False)}")

    if "zabbix" in data:
        _print_section("ZABBIX")
        zabbix = data["zabbix"]
        _dump("auth_ok", zabbix.get("auth_ok"))
        _dump("host.get raw", zabbix.get("host_get_response"))
        _dump("processed", zabbix.get("processed"))
        if zabbix.get("error"):
            print(f"ERROR: {zabbix['error']}")

    if "clickhouse" in data:
        _print_section("CLICKHOUSE")
        ch = data["clickhouse"]
        _dump("sample rows", ch.get("sample_rows"))
        _dump("aggregated by port", ch.get("aggregated_rows"))
        _dump("processed", ch.get("processed"))
        if ch.get("fdb_port_analysis"):
            _dump("FDB port shape analysis", ch["fdb_port_analysis"])
        if ch.get("error"):
            print(f"ERROR: {ch['error']}")

    if "snmp" in data:
        _print_section("SNMP")
        snmp = data["snmp"]
        _dump("raw walk", snmp.get("raw_walk"))
        _dump("processed", snmp.get("processed"))
        if snmp.get("analysis"):
            _dump("SNMP port name analysis", snmp["analysis"])
        if snmp.get("error"):
            print(f"ERROR: {snmp['error']}")

    if "context" in data:
        _print_section("FULL CONTEXT (analyze_switch)")
        context = data["context"]
        if len(context) > 4000:
            print(context[:4000])
            print(f"\n... truncated, total {len(context)} chars. Use --save for full dump.")
        else:
            print(context)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Диагностика Zabbix / ClickHouse / SNMP для switcher")
    parser.add_argument("ip", help="IP коммутатора")
    parser.add_argument("--query", help="Текст запроса для analyze_switch")
    parser.add_argument(
        "--source",
        choices=["all", "zabbix", "clickhouse", "snmp"],
        default="all",
        help="Какой источник опрашивать",
    )
    parser.add_argument("--days", type=int, default=30, help="Глубина выборки FDB в днях")
    parser.add_argument("--snmp-limit", type=int, default=10, help="Сколько SNMP OID показать в сыром виде")
    parser.add_argument("--row-limit", type=int, default=30, help="Сколько строк списков показывать в консоли")
    parser.add_argument("--save", help="Сохранить полный JSON-дамп в файл")
    parser.add_argument("--include-context", action="store_true", help="Добавить analyze_switch context")
    return parser.parse_args()


async def main_async(args: argparse.Namespace) -> None:
    switch_ip = extract_ip_from_query(args.ip) or args.ip
    data = await collect_switch_probe(
        switch_ip=switch_ip,
        source=args.source,  # type: ignore[arg-type]
        days=args.days,
        snmp_limit=args.snmp_limit,
        row_limit=args.row_limit,
        include_context=args.include_context,
        query=args.query,
    )

    if args.save:
        path = Path(args.save)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        print(f"Full probe saved to: {path}")
    else:
        _print_probe(data)


def main() -> None:
    logging.basicConfig(level=logging.WARNING)
    args = parse_args()
    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
