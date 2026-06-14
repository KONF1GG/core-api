"""
Модуль для анализа коммутаторов и расчета свободных портов.

Поддерживает работу с Zabbix, ClickHouse и SNMP для получения данных о коммутаторах.
"""

import json
import re
import requests
import clickhouse_connect
from typing import Dict, List, Any, Optional

from pysnmp.hlapi.v3arch.asyncio import (
    SnmpEngine,
    CommunityData,
    UdpTransportTarget,
    ContextData,
    ObjectType,
    ObjectIdentity,
    next_cmd,
)

import asyncio


from config import (
    ZABBIX_URL,
    ZABBIX_USER,
    ZABBIX_PASSWORD,
    CLICKHOUSE_HOST,
    CLICKHOUSE_PORT,
    CLICKHOUSE_USER,
    CLICKHOUSE_PASSWORD,
    CLICKHOUSE_DB,
    SNMP_COMMUNITY,
)
from logger_config import get_logger

logger = get_logger(__name__)

# === СПРАВОЧНИК МОДЕЛЕЙ КОММУТАТОРОВ ===
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
    """
    Извлекает IP-адрес из текста запроса.
    
    Args:
        query: Текст запроса
        
    Returns:
        IP-адрес или None
    """
    ip_pattern = r'\b(?:\d{1,3}\.){3}\d{1,3}\b'
    match = re.search(ip_pattern, query)
    return match.group() if match else None


def get_switches_from_zabbix(switch_ip: str) -> List[Dict[str, Any]]:
    """
    Получает информацию о коммутаторе из Zabbix по IP-адресу.
    
    Args:
        switch_ip: IP-адрес коммутатора
        
    Returns:
        Список словарей с информацией о коммутаторах
    """
    endpoint = f"{ZABBIX_URL}/api_jsonrpc.php"
    
    auth_payload = {
        "jsonrpc": "2.0",
        "method": "user.login",
        "params": {"username": ZABBIX_USER, "password": ZABBIX_PASSWORD},
        "id": 1
    }

    try:
        auth_resp = requests.post(
            endpoint,
            json=auth_payload,
            headers={"Content-Type": "application/json-rpc"},
            timeout=10
        )
        auth_token = auth_resp.json().get("result")

        if not auth_token:
            logger.error("Ошибка авторизации в Zabbix")
            return []

        host_params = {
            "output": ["hostid", "host", "name"],
            "selectInterfaces": ["ip"],
            "selectGroups": ["name"],
            "filter": {"ip": [switch_ip]}
        }
        
        hosts_payload = {
            "jsonrpc": "2.0",
            "method": "host.get",
            "params": host_params,
            "auth": auth_token,
            "id": 2
        }
        
        hosts_resp = requests.post(
            endpoint, 
            json=hosts_payload, 
            headers={"Content-Type": "application/json-rpc"}, 
            timeout=10
        )
        hosts_data = hosts_resp.json().get("result", [])
        
        if not hosts_data:
            logger.warning(f"Коммутатор с IP {switch_ip} не найден в Zabbix")
            return []
        
        switches = []
        for h in hosts_data:
            name = h.get("name", "")
            ip = h["interfaces"][0]["ip"] if h.get("interfaces") else "N/A"
            
            model = "Unknown"
            for m in SWITCH_MODELS.keys():
                if m.lower() in name.lower():
                    model = m
                    break
            
            switches.append({
                "name": name,
                "ip": ip,
                "model": model,
                "expected_ports": SWITCH_MODELS.get(model, {}).get("ports", 0)
            })
        
        logger.info(f"Получена информация о {len(switches)} коммутаторах из Zabbix")
        return switches
    
    except Exception as e:
        logger.error(f"Ошибка при запросе к Zabbix: {e}")
        return []


def get_fdb_from_clickhouse(switch_ip: str, days: int = 30) -> List[Dict[str, Any]]:
    """
    Получает таблицу FDB из ClickHouse для указанного коммутатора.
    
    Args:
        switch_ip: IP-адрес коммутатора
        days: За сколько дней искать записи FDB
        
    Returns:
        Список словарей с данными FDB
    """
    try:
        client = clickhouse_connect.get_client(
            host=CLICKHOUSE_HOST,
            port=int(CLICKHOUSE_PORT),
            username=CLICKHOUSE_USER,
            password=CLICKHOUSE_PASSWORD,
            database=CLICKHOUSE_DB
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
            logger.warning(f"Записей FDB для коммутатора {switch_ip} за последние {days} дней не найдено")
            return []
        
        fdb_data = []
        for row in result.result_rows:
            fdb_data.append({
                "port": row[0],
                "mac_count": row[1],
                "last_seen": str(row[2])
            })
        
        logger.info(f"Получено {len(fdb_data)} записей FDB из ClickHouse")
        return fdb_data
    
    except Exception as e:
        logger.error(f"Ошибка при запросе к ClickHouse: {e}")
        return []


async def snmp_getnext(switch_ip: str, oid: str, community: str = SNMP_COMMUNITY, timeout: int = 2) -> List[tuple]:
    """
    Выполняет SNMP GETNEXT запрос используя pysnmp 7.x asyncio API.
    
    Args:
        switch_ip: IP-адрес коммутатора
        oid: OID для запроса
        community: SNMP community string
        timeout: Таймаут в секундах
        
    Returns:
        Список кортежей (oid, value)
    """
    try:
        from pysnmp.entity.rfc3413 import cmdgen
        from pysnmp.proto.api import v2c
        from pysnmp.carrier.asyncio.dgram import UdpTransport
        
        # Создаем SNMP engine
        snmp_engine = cmdgen.SnmpEngine()
        
        # Создаем транспорт
        transport = UdpTransport().openClientMode()
        await transport.openTransport()
        
        # Создаем командный генератор
        cmd_gen = cmdgen.NextCommandGenerator()
        
        # Отправляем запрос
        error_indication, error_status, error_index, var_binds = await cmd_gen.sendVarBinds(
            snmp_engine,
            cmdgen.UdpTransportTarget((switch_ip, 161)),
            cmdgen.CommunityData(community),
            v2c.ObjectType(v2c.ObjectIdentity(oid)),
        )
        
        await transport.closeTransport()
        
        if error_indication:
            raise Exception(f"SNMP error: {error_indication}")
        
        if error_status:
            raise Exception(f"SNMP error status: {error_status}")
        
        # Парсим результаты
        results = []
        for var_bind in var_binds:
            for oid, value in var_bind:
                results.append((str(oid), str(value)))
        
        return results
    
    except Exception as e:
        logger.error(f"SNMP GETNEXT ошибка: {e}")
        return []


async def snmp_walk(host: str, oid: str):
    result = []

    transport = await UdpTransportTarget.create(
        (host, 161),
        timeout=2,
        retries=1,
    )

    current_oid = ObjectIdentity(oid)

    while True:
        error_indication, error_status, error_index, var_binds = await next_cmd(
            SnmpEngine(),
            CommunityData(SNMP_COMMUNITY),
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
    """
    Получение списка портов через SNMP.
    """

    try:
        port_name_oid = "1.3.6.1.2.1.2.2.1.2"
        port_status_oid = "1.3.6.1.2.1.2.2.1.8"
        vlan_oid = "1.3.6.1.2.1.17.7.1.4.5.1.1"

        port_names = {}
        port_statuses = {}
        port_vlans = {}

        names = await snmp_walk(switch_ip, port_name_oid)

        for oid, value in names:
            try:
                idx = int(oid.split(".")[-1])
                port_names[idx] = value
            except Exception:
                pass

        statuses = await snmp_walk(switch_ip, port_status_oid)

        for oid, value in statuses:
            try:
                idx = int(oid.split(".")[-1])
                port_statuses[idx] = (
                    "up"
                    if int(value) == 1
                    else "down"
                )
            except Exception:
                pass

        try:
            vlans = await snmp_walk(switch_ip, vlan_oid)

            for oid, value in vlans:
                try:
                    idx = int(oid.split(".")[-1])
                    port_vlans[idx] = int(value)
                except Exception:
                    pass

        except Exception:
            logger.warning(
                "Не удалось получить VLAN через SNMP"
            )

        ports = []

        for idx in sorted(port_names):
            ports.append(
                {
                    "port": port_names[idx],
                    "index": idx,
                    "status": port_statuses.get(
                        idx,
                        "unknown",
                    ),
                    "vlan_untagged": port_vlans.get(
                        idx,
                        1,
                    ),
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
        logger.exception("SNMP error")

        return {
            "available": False,
            "error": str(e),
        }

def get_switch_model_info(model: str) -> Dict[str, Any]:
    """
    Получает информацию о модели коммутатора из справочника.
    
    Args:
        model: Модель коммутатора
        
    Returns:
        Словарь с информацией о модели
    """
    info = SWITCH_MODELS.get(model)
    if not info:
        return {
            "error": f"Модель '{model}' не найдена в справочнике",
            "available_models": list(SWITCH_MODELS.keys())
        }
    
    return {
        "model": model,
        "ports": info["ports"],
        "type": info["type"]
    }


async def analyze_switch(query: str) -> str:
    """
    Анализирует запрос о коммутаторе и собирает данные из разных источников.
    
    Args:
        query: Запрос пользователя
        
    Returns:
        Строка с данными для анализа AI
    """
    logger.info(f"Анализ запроса о коммутаторе: {query}")
    
    # Извлекаем IP из запроса
    switch_ip = extract_ip_from_query(query)
    
    if not switch_ip:
        return "Ошибка: не удалось найти IP-адрес коммутатора в запросе. Пожалуйста, укажите IP-адрес."
    
    context_parts = []
    
    # 1. Получаем данные из Zabbix
    zabbix_data = get_switches_from_zabbix(switch_ip)
    if zabbix_data:
        context_parts.append(f"=== ДАННЫЕ ZABBIX ===\n{json.dumps(zabbix_data, ensure_ascii=False, indent=2)}")
    else:
        context_parts.append("=== ДАННЫЕ ZABBIX ===\nКоммутатор не найден или ошибка подключения")
    
    # 2. Получаем данные из ClickHouse
    fdb_data = get_fdb_from_clickhouse(switch_ip)
    if fdb_data:
        context_parts.append(f"\n=== ДАННЫЕ FDB (ClickHouse) ===\n{json.dumps(fdb_data, ensure_ascii=False, indent=2)}")
    else:
        context_parts.append("\n=== ДАННЫЕ FDB (ClickHouse) ===\nДанные не найдены или ошибка подключения")
    
    # 3. Получаем данные через SNMP
    snmp_data = await get_port_status_via_snmp(switch_ip)
    if snmp_data.get("available"):
        context_parts.append(f"\n=== ДАННЫЕ SNMP ===\n{json.dumps(snmp_data['ports'], ensure_ascii=False, indent=2)}")
    else:
        context_parts.append(f"\n=== ДАННЫЕ SNMP ===\nНедоступно: {snmp_data.get('error', 'Неизвестная ошибка')}")

    return "\n".join(context_parts)
