"""Анализ сетевых коммутаторов через Zabbix, ClickHouse и SNMP."""

import asyncio
import json
import re
from typing import Any, Optional

import clickhouse_connect
import requests
from pysnmp.hlapi.v3arch.asyncio import (
    CommunityData,
    ContextData,
    ObjectIdentity,
    ObjectType,
    SnmpEngine,
    UdpTransportTarget,
    next_cmd,
)

from mcp_servers.switcher import config
from shared.logging import get_logger

logger = get_logger(__name__)

SWITCH_MODELS = {
    "DES-3028": {"ports": 28, "type": "D-Link"},
    "DES-3200-28": {"ports": 28, "type": "D-Link"},
    "DES-3526": {"ports": 26, "type": "D-Link"},
    "DES-3016": {"ports": 16, "type": "D-Link"},
    "S5720-28P": {"ports": 28, "type": "Huawei"},
    "S5720-52P": {"ports": 52, "type": "Huawei"},
    "S3700-28P": {"ports": 28, "type": "Huawei"},
    "RG-S2910-24GT4SFP": {"ports": 24, "type": "Ruijie"},
}


def extract_ip_from_query(query: str) -> Optional[str]:
    ip_pattern = r"\b(?:\d{1,3}\.){3}\d{1,3}\b"
    match = re.search(ip_pattern, query)
    return match.group() if match else None


def get_switches_from_zabbix(switch_ip: str) -> list[dict[str, Any]]:
    endpoint = f"{config.ZABBIX_URL}/api_jsonrpc.php"

    auth_payload = {
        "jsonrpc": "2.0",
        "method": "user.login",
        "params": {"username": config.ZABBIX_USER, "password": config.ZABBIX_PASSWORD},
        "id": 1,
    }

    try:
        auth_resp = requests.post(
            endpoint,
            json=auth_payload,
            headers={"Content-Type": "application/json-rpc"},
            timeout=10,
        )
        auth_token = auth_resp.json().get("result")

        if not auth_token:
            logger.error("Ошибка авторизации в Zabbix")
            return []

        host_params = {
            "output": ["hostid", "host", "name"],
            "selectInterfaces": ["ip"],
            "selectGroups": ["name"],
            "filter": {"ip": [switch_ip]},
        }

        hosts_payload = {
            "jsonrpc": "2.0",
            "method": "host.get",
            "params": host_params,
            "auth": auth_token,
            "id": 2,
        }

        hosts_resp = requests.post(
            endpoint,
            json=hosts_payload,
            headers={"Content-Type": "application/json-rpc"},
            timeout=10,
        )
        hosts_data = hosts_resp.json().get("result", [])

        if not hosts_data:
            logger.warning("Коммутатор с IP %s не найден в Zabbix", switch_ip)
            return []

        switches = []
        for host in hosts_data:
            name = host.get("name", "")
            ip = host["interfaces"][0]["ip"] if host.get("interfaces") else "N/A"

            model = "Unknown"
            for model_name in SWITCH_MODELS:
                if model_name.lower() in name.lower():
                    model = model_name
                    break

            switches.append(
                {
                    "name": name,
                    "ip": ip,
                    "model": model,
                    "expected_ports": SWITCH_MODELS.get(model, {}).get("ports", 0),
                }
            )

        logger.info("Получена информация о %d коммутаторах из Zabbix", len(switches))
        return switches

    except Exception as e:
        logger.error("Ошибка при запросе к Zabbix: %s", e)
        return []


def get_fdb_from_clickhouse(switch_ip: str, days: int = 30) -> list[dict[str, Any]]:
    try:
        client = clickhouse_connect.get_client(
            host=config.CLICKHOUSE_HOST,
            port=int(config.CLICKHOUSE_PORT),
            username=config.CLICKHOUSE_USER,
            password=config.CLICKHOUSE_PASSWORD,
            database=config.CLICKHOUSE_DB,
        )

        query = f"""
        SELECT
            port,
            count(DISTINCT mac) as mac_count,
            max(dt) as last_seen
        FROM sw_fdb
        WHERE sw_ip = '{switch_ip}'
          AND dt >= now() - INTERVAL {days} DAY
        GROUP BY port
        ORDER BY port
        """

        result = client.query(query)

        if not result.result_rows:
            logger.warning(
                "Записей FDB для коммутатора %s за последние %d дней не найдено",
                switch_ip,
                days,
            )
            return []

        fdb_data = []
        for row in result.result_rows:
            fdb_data.append(
                {
                    "port": row[0],
                    "mac_count": row[1],
                    "last_seen": str(row[2]),
                }
            )

        logger.info("Получено %d записей FDB из ClickHouse", len(fdb_data))
        return fdb_data

    except Exception as e:
        logger.error("Ошибка при запросе к ClickHouse: %s", e)
        return []


async def snmp_walk(host: str, oid: str):
    result = []

    transport = await UdpTransportTarget.create(
        (host, 161),
        timeout=2,
        retries=1,
    )

    snmp_engine = SnmpEngine()
    current_oid = ObjectIdentity(oid)

    while True:
        error_indication, error_status, error_index, var_binds = await next_cmd(
            snmp_engine,
            CommunityData(config.SNMP_COMMUNITY),
            transport,
            ContextData(),
            ObjectType(current_oid),
        )

        if error_indication:
            raise RuntimeError(str(error_indication))

        if error_status:
            raise RuntimeError(str(error_status))

        if not var_binds:
            break

        next_oid, value = var_binds[0]
        oid_str = str(next_oid)

        if not oid_str.startswith(oid):
            break

        result.append((oid_str, str(value)))
        current_oid = ObjectIdentity(oid_str)

    return result


async def get_port_status_via_snmp(switch_ip: str) -> dict:
    try:
        port_name_oid = "1.3.6.1.2.1.2.2.1.2"
        port_status_oid = "1.3.6.1.2.1.2.2.1.8"
        vlan_oid = "1.3.6.1.2.1.17.7.1.4.5.1.1"

        port_names = {}
        port_statuses = {}
        port_vlans = {}

        names, statuses, vlans = await asyncio.gather(
            snmp_walk(switch_ip, port_name_oid),
            snmp_walk(switch_ip, port_status_oid),
            snmp_walk(switch_ip, vlan_oid),
            return_exceptions=True,
        )

        if isinstance(names, Exception):
            raise names

        for oid, value in names:
            try:
                idx = int(oid.split(".")[-1])
                port_names[idx] = value
            except Exception:
                pass

        if not isinstance(statuses, Exception):
            for oid, value in statuses:
                try:
                    idx = int(oid.split(".")[-1])
                    port_statuses[idx] = "up" if int(value) == 1 else "down"
                except Exception:
                    pass

        if isinstance(vlans, Exception):
            logger.warning("Не удалось получить VLAN через SNMP")
        else:
            for oid, value in vlans:
                try:
                    idx = int(oid.split(".")[-1])
                    port_vlans[idx] = int(value)
                except Exception:
                    pass

        ports = []
        for idx in sorted(port_names):
            ports.append(
                {
                    "port": port_names[idx],
                    "index": idx,
                    "status": port_statuses.get(idx, "unknown"),
                    "vlan_untagged": port_vlans.get(idx, 1),
                }
            )

        if not ports:
            return {
                "available": False,
                "error": "Порты не найдены",
            }

        return {
            "available": True,
            "ports": ports,
        }

    except Exception as e:
        logger.exception("Ошибка SNMP")
        return {
            "available": False,
            "error": str(e),
        }


async def analyze_switch(query: str) -> str:
    logger.info("Анализ запроса о коммутаторе: %s", query)

    switch_ip = extract_ip_from_query(query)
    if not switch_ip:
        return (
            "Ошибка: не удалось найти IP-адрес коммутатора в запросе. "
            "Пожалуйста, укажите IP-адрес."
        )

    zabbix_data, fdb_data, snmp_data = await asyncio.gather(
        asyncio.to_thread(get_switches_from_zabbix, switch_ip),
        asyncio.to_thread(get_fdb_from_clickhouse, switch_ip),
        get_port_status_via_snmp(switch_ip),
    )

    context_parts = []

    if zabbix_data:
        context_parts.append(
            f"=== ДАННЫЕ ZABBIX ===\n{json.dumps(zabbix_data, ensure_ascii=False, indent=2)}"
        )
    else:
        context_parts.append(
            "=== ДАННЫЕ ZABBIX ===\nКоммутатор не найден или ошибка подключения"
        )

    if fdb_data:
        context_parts.append(
            f"\n=== ДАННЫЕ FDB (ClickHouse) ===\n"
            f"{json.dumps(fdb_data, ensure_ascii=False, indent=2)}"
        )
    else:
        context_parts.append(
            "\n=== ДАННЫЕ FDB (ClickHouse) ===\nДанные не найдены или ошибка подключения"
        )

    if snmp_data.get("available"):
        context_parts.append(
            f"\n=== ДАННЫЕ SNMP ===\n"
            f"{json.dumps(snmp_data['ports'], ensure_ascii=False, indent=2)}"
        )
    else:
        context_parts.append(
            f"\n=== ДАННЫЕ SNMP ===\nНедоступно: {snmp_data.get('error', 'Неизвестная ошибка')}"
        )

    return "\n".join(context_parts)
