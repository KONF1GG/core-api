"""
Диагностика источников данных для switcher (Zabbix, ClickHouse, SNMP).
"""

from __future__ import annotations

import asyncio
import re
from collections import Counter
from typing import Any, Literal

import clickhouse_connect
import requests

from config import (
    CLICKHOUSE_DB,
    CLICKHOUSE_HOST,
    CLICKHOUSE_PASSWORD,
    CLICKHOUSE_PORT,
    CLICKHOUSE_USER,
    SNMP_COMMUNITY,
    ZABBIX_PASSWORD,
    ZABBIX_URL,
    ZABBIX_USER,
)
from switcher import (
    analyze_switch,
    extract_ip_from_query,
    get_fdb_from_clickhouse,
    get_port_status_via_snmp,
    get_switches_from_zabbix,
    snmp_walk,
)

ProbeSource = Literal["all", "zabbix", "clickhouse", "snmp"]


def _truncate_list(items: list[Any], limit: int | None) -> dict[str, Any]:
    if limit is None or len(items) <= limit:
        return {"items": items, "total": len(items)}
    return {
        "items": items[:limit],
        "total": len(items),
        "truncated": f"shown {limit} of {len(items)}",
    }


def _truncate_rows(data: dict[str, Any], limit: int | None) -> dict[str, Any]:
    rows = data.get("rows", [])
    if limit is None or len(rows) <= limit:
        return {**data, "total": len(rows)}
    return {
        **data,
        "rows": rows[:limit],
        "total": len(rows),
        "truncated": f"shown {limit} of {len(rows)}",
    }


def _zabbix_request(method: str, params: dict, auth: str | None = None) -> dict:
    payload: dict[str, Any] = {
        "jsonrpc": "2.0",
        "method": method,
        "params": params,
        "id": 1,
    }
    if auth:
        payload["auth"] = auth

    response = requests.post(
        f"{ZABBIX_URL}/api_jsonrpc.php",
        json=payload,
        headers={"Content-Type": "application/json-rpc"},
        timeout=15,
    )
    response.raise_for_status()
    return response.json()


def probe_zabbix(switch_ip: str) -> dict[str, Any]:
    result: dict[str, Any] = {"switch_ip": switch_ip, "ok": False}

    login = _zabbix_request(
        "user.login",
        {"username": ZABBIX_USER, "password": ZABBIX_PASSWORD},
    )
    result["auth_ok"] = bool(login.get("result"))

    token = login.get("result")
    if not token:
        result["error"] = "Zabbix auth failed"
        return result

    hosts = _zabbix_request(
        "host.get",
        {
            "output": ["hostid", "host", "name"],
            "selectInterfaces": ["interfaceid", "ip", "port", "type", "main"],
            "selectGroups": ["groupid", "name"],
            "filter": {"ip": [switch_ip]},
        },
        auth=token,
    )
    result["host_get_response"] = hosts
    result["processed"] = get_switches_from_zabbix(switch_ip)
    result["ok"] = bool(hosts.get("result"))
    return result


def probe_clickhouse(switch_ip: str, days: int) -> dict[str, Any]:
    result: dict[str, Any] = {"switch_ip": switch_ip, "days": days, "ok": False}

    try:
        client = clickhouse_connect.get_client(
            host=CLICKHOUSE_HOST,
            port=int(CLICKHOUSE_PORT),
            username=CLICKHOUSE_USER,
            password=CLICKHOUSE_PASSWORD,
            database=CLICKHOUSE_DB,
        )

        sample_query = f"""
        SELECT port, mac, dt
        FROM sw_fdb
        WHERE sw_ip = '{switch_ip}'
          AND dt >= now() - INTERVAL {days} DAY
        ORDER BY dt DESC
        LIMIT 10
        """
        agg_query = f"""
        SELECT
            port,
            count(DISTINCT mac) AS mac_count,
            max(dt) AS last_seen
        FROM sw_fdb
        WHERE sw_ip = '{switch_ip}'
          AND dt >= now() - INTERVAL {days} DAY
        GROUP BY port
        ORDER BY port
        """

        sample = client.query(sample_query)
        aggregated = client.query(agg_query)

        result["sample_rows"] = {
            "columns": sample.column_names,
            "rows": sample.result_rows,
        }
        result["aggregated_rows"] = {
            "columns": aggregated.column_names,
            "rows": aggregated.result_rows,
        }
        result["processed"] = get_fdb_from_clickhouse(switch_ip, days=days)
        result["ok"] = bool(aggregated.result_rows)
    except Exception as exc:
        result["error"] = str(exc)

    return result


def extract_port_number(value: str | int) -> int | None:
    if isinstance(value, int):
        return value

    text = str(value).strip()
    if text.isdigit():
        return int(text)

    match = re.search(r"(\d+)\s*$", text)
    if match:
        return int(match.group(1))

    numbers = re.findall(r"\d+", text)
    if numbers:
        return int(numbers[-1])

    return None


def is_virtual_port_name(name: str) -> bool:
    lowered = name.lower()
    virtual_markers = (
        "loopback",
        "vlan",
        "management",
        "mgmt",
        "null",
        "stack",
        "bridge",
        "tunnel",
    )
    return any(marker in lowered for marker in virtual_markers)


def is_uplink_port_name(name: str) -> bool:
    lowered = name.lower()
    return any(marker in lowered for marker in ("uplink", "trunk", "sfp", "combo"))


async def probe_snmp(switch_ip: str, limit: int) -> dict[str, Any]:
    result: dict[str, Any] = {"switch_ip": switch_ip, "ok": False}

    try:
        port_name_oid = "1.3.6.1.2.1.2.2.1.2"
        port_status_oid = "1.3.6.1.2.1.2.2.1.8"
        vlan_oid = "1.3.6.1.2.1.17.7.1.4.5.1.1"

        names, statuses, vlans = await asyncio.gather(
            snmp_walk(switch_ip, port_name_oid),
            snmp_walk(switch_ip, port_status_oid),
            snmp_walk(switch_ip, vlan_oid),
            return_exceptions=True,
        )

        result["raw_walk"] = {
            "ifDescr": names[:limit] if isinstance(names, list) else str(names),
            "ifOperStatus": statuses[:limit] if isinstance(statuses, list) else str(statuses),
            "vlan_untagged": vlans[:limit] if isinstance(vlans, list) else str(vlans),
            "counts": {
                "ifDescr": len(names) if isinstance(names, list) else 0,
                "ifOperStatus": len(statuses) if isinstance(statuses, list) else 0,
                "vlan_untagged": len(vlans) if isinstance(vlans, list) else 0,
            },
        }

        processed = await get_port_status_via_snmp(switch_ip)
        result["processed"] = processed
        result["ok"] = processed.get("available", False)

        if processed.get("available"):
            ports = processed["ports"]
            name_samples = Counter(port["port"] for port in ports[:20])
            parsed_numbers = [
                extract_port_number(port["port"])
                for port in ports
                if not is_virtual_port_name(port["port"])
            ]
            result["analysis"] = {
                "total_interfaces": len(ports),
                "physical_like_ports": sum(
                    1 for port in ports if not is_virtual_port_name(port["port"])
                ),
                "virtual_ports": [
                    port["port"] for port in ports if is_virtual_port_name(port["port"])
                ],
                "uplink_like_ports": [
                    port["port"] for port in ports if is_uplink_port_name(port["port"])
                ],
                "status_counts": dict(Counter(port["status"] for port in ports)),
                "name_samples": dict(name_samples),
                "parsed_port_numbers": sorted({n for n in parsed_numbers if n is not None}),
                "unparsed_names": [
                    port["port"]
                    for port in ports
                    if extract_port_number(port["port"]) is None
                    and not is_virtual_port_name(port["port"])
                ],
            }
    except Exception as exc:
        result["error"] = str(exc)

    return result


def probe_fdb_port_shapes(fdb_rows: list[dict[str, Any]]) -> dict[str, Any]:
    ports = [row.get("port") for row in fdb_rows]
    parsed = [extract_port_number(port) for port in ports if port is not None]
    return {
        "raw_port_values": ports[:30],
        "raw_port_types": dict(Counter(type(port).__name__ for port in ports)),
        "parsed_numbers": sorted({n for n in parsed if n is not None}),
        "unparsed_values": [port for port in ports if extract_port_number(port) is None],
    }


async def collect_switch_probe(
    switch_ip: str,
    source: ProbeSource = "all",
    days: int = 30,
    snmp_limit: int = 10,
    row_limit: int = 30,
    include_context: bool = False,
    query: str | None = None,
) -> dict[str, Any]:
    ip = extract_ip_from_query(switch_ip) or switch_ip
    result: dict[str, Any] = {
        "switch_ip": ip,
        "source": source,
        "config": {
            "zabbix_url": ZABBIX_URL,
            "clickhouse": f"{CLICKHOUSE_HOST}:{CLICKHOUSE_PORT}/{CLICKHOUSE_DB}",
            "snmp_community_set": bool(SNMP_COMMUNITY),
        },
    }

    if source in ("all", "zabbix"):
        zabbix = await asyncio.to_thread(probe_zabbix, ip)
        result["zabbix"] = {
            **zabbix,
            "processed": _truncate_list(zabbix.get("processed") or [], row_limit),
        }

    if source in ("all", "clickhouse"):
        clickhouse = await asyncio.to_thread(probe_clickhouse, ip, days)
        processed = clickhouse.get("processed") or []
        result["clickhouse"] = {
            **clickhouse,
            "sample_rows": clickhouse.get("sample_rows"),
            "aggregated_rows": _truncate_rows(
                clickhouse.get("aggregated_rows") or {"rows": []},
                row_limit,
            ),
            "processed": _truncate_list(processed, row_limit),
            "fdb_port_analysis": probe_fdb_port_shapes(processed) if processed else None,
        }

    if source in ("all", "snmp"):
        snmp = await probe_snmp(ip, limit=snmp_limit)
        processed = snmp.get("processed") or {}
        ports = processed.get("ports") or []
        result["snmp"] = {
            **snmp,
            "processed": {
                **processed,
                "ports": _truncate_list(ports, row_limit) if ports else [],
            },
        }

    if include_context and source == "all":
        context_query = query or f"свободные порты на {ip}"
        result["context"] = await analyze_switch(context_query)

    return result
