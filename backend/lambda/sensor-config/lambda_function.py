from spill_common import observed, body_object, integer

"""
sensor_config Lambda — Python 3.12 (psycopg2)
──────────────────────────────────────────────
GET  /config/{device_id}              → 读取 sensor active 状态
POST /config/{device_id}/update       → 更新 sensor active
POST /config/push                     → MQTT 推送 sensor active 到设备
GET  /threshold/{device_id}           → 读取 sensor threshold
POST /threshold/{device_id}/update    → 更新 sensor threshold
POST /threshold/push                  → MQTT 推送 threshold 到设备

Environment variables:
  DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASS, IOT_ENDPOINT
"""

import os
import json
import re
import psycopg2
import boto3
from datetime import datetime, timezone

DB_HOST = os.environ["DB_HOST"]
DB_PORT = int(os.environ.get("DB_PORT", "5432"))
DB_NAME = os.environ["DB_NAME"]
DB_USER = os.environ["DB_USER"]
DB_PASS = os.environ["DB_PASS"]
IOT_ENDPOINT = os.environ["IOT_ENDPOINT"]

iot_data = boto3.client(
    "iot-data",
    region_name=os.getenv("AWS_REGION", "eu-north-1"),
    endpoint_url="https://" + IOT_ENDPOINT,
)

# ── 路由入口 ─────────────────────────────────────────────────────────────────


@observed("sensor_config", api=True)
def lambda_handler(event, context):
    method = event.get("httpMethod", "")
    path = event.get("path", "")

    if method == "OPTIONS":
        return _resp(200, {})

    # GET /config/{device_id}
    if method == "GET":
        m = re.match(r"^/config/([^/]+)$", path)
        if m:
            return handle_get(m.group(1))

    # GET /threshold/{device_id}
    if method == "GET":
        m = re.match(r"^/threshold/([^/]+)$", path)
        if m:
            return handle_threshold_get(m.group(1))

    # POST /config/push  ← 静态路径优先
    if method == "POST" and path == "/config/push":
        body = body_object(event)
        return handle_push(body)

    # POST /threshold/push  ← 静态路径优先
    if method == "POST" and path == "/threshold/push":
        body = body_object(event)
        return handle_threshold_push(body)

    # POST /config/{device_id}/update
    if method == "POST":
        m = re.match(r"^/config/([^/]+)/update$", path)
        if m:
            body = body_object(event)
            return handle_update(m.group(1), body)

    # POST /threshold/{device_id}/update
    if method == "POST":
        m = re.match(r"^/threshold/([^/]+)/update$", path)
        if m:
            body = body_object(event)
            return handle_threshold_update(m.group(1), body)

    return _resp(404, {"ok": False, "error": f"No route for {method} {path}"})


# ── Config 处理函数 ───────────────────────────────────────────────────────────


def handle_get(device_id: str):
    rows = _db_fetch(
        "SELECT sensor_id, active FROM sensor_config "
        "WHERE device_id = %s ORDER BY sensor_id",
        (device_id,),
    )
    sensors = [{"sensor_id": sid, "active": active} for sid, active in rows]
    return _resp(200, {"ok": True, "device_id": device_id, "sensors": sensors})


def handle_update(device_id: str, body: dict):
    try:
        sensor_id = integer(body["sensor_id"], "sensor_id")
        active = body["active"]
        if not isinstance(active, bool):
            raise ValueError("active must be a JSON boolean")
    except (KeyError, ValueError, TypeError) as e:
        return _resp(400, {"ok": False, "error": str(e)})

    updated = _db_execute(
        "UPDATE sensor_config SET active = %s WHERE device_id = %s AND sensor_id = %s",
        (active, device_id, sensor_id),
    )
    if updated == 0:
        return _resp(404, {"ok": False, "error": "row not found"})
    return _resp(
        200,
        {"ok": True, "device_id": device_id, "sensor_id": sensor_id, "active": active},
    )


def handle_push(body: dict):
    device_id = body.get("device_id")
    if not device_id:
        return _resp(400, {"ok": False, "error": "missing device_id"})

    rows = _db_fetch(
        "SELECT sensor_id, active FROM sensor_config "
        "WHERE device_id = %s ORDER BY sensor_id",
        (device_id,),
    )
    if not rows:
        return _resp(404, {"ok": False, "error": f"no config rows for {device_id}"})

    sensors = {str(sid): active for sid, active in rows}
    payload = json.dumps({"sensors": sensors})
    topic = f"config/{device_id}/sensors"

    iot_data.publish(topic=topic, qos=1, payload=payload.encode("utf-8"))

    print(
        json.dumps(
            {
                "msg": "Config published",
                "device_id": device_id,
                "topic": topic,
                "payload": payload,
                "ts": datetime.now(timezone.utc).isoformat(),
            }
        )
    )
    return _resp(
        200, {"ok": True, "device_id": device_id, "topic": topic, "sensors": sensors}
    )


# ── Threshold 处理函数 ────────────────────────────────────────────────────────


def handle_threshold_get(device_name: str):
    rows = _db_fetch(
        "SELECT sensor_id, threshold_value FROM sensor_thresholds "
        "WHERE device_name = %s ORDER BY sensor_id",
        (device_name,),
    )
    thresholds = [{"sensor_id": sid, "threshold_value": val} for sid, val in rows]
    return _resp(
        200, {"ok": True, "device_name": device_name, "thresholds": thresholds}
    )


def handle_threshold_update(device_name: str, body: dict):
    try:
        sensor_id = integer(body["sensor_id"], "sensor_id")
        threshold_value = integer(body["threshold_value"], "threshold_value")
    except (KeyError, ValueError, TypeError) as e:
        return _resp(400, {"ok": False, "error": str(e)})

    updated = _db_execute(
        "UPDATE sensor_thresholds SET threshold_value = %s, updated_at = now() "
        "WHERE device_name = %s AND sensor_id = %s",
        (threshold_value, device_name, sensor_id),
    )
    if updated == 0:
        return _resp(404, {"ok": False, "error": "row not found"})
    return _resp(
        200,
        {
            "ok": True,
            "device_name": device_name,
            "sensor_id": sensor_id,
            "threshold_value": threshold_value,
        },
    )


def handle_threshold_push(body: dict):
    device_name = body.get("device_id")
    if not device_name:
        return _resp(400, {"ok": False, "error": "missing device_id"})

    rows = _db_fetch(
        "SELECT sensor_id, threshold_value FROM sensor_thresholds "
        "WHERE device_name = %s ORDER BY sensor_id",
        (device_name,),
    )
    if not rows:
        return _resp(
            404, {"ok": False, "error": f"no threshold rows for {device_name}"}
        )

    thresholds = {str(sid): val for sid, val in rows}
    payload = json.dumps({"thresholds": thresholds})
    topic = f"config/{device_name}/thresholds"

    iot_data.publish(topic=topic, qos=1, payload=payload.encode("utf-8"))

    print(
        json.dumps(
            {
                "msg": "Threshold published",
                "device_name": device_name,
                "topic": topic,
                "payload": payload,
                "ts": datetime.now(timezone.utc).isoformat(),
            }
        )
    )
    return _resp(
        200,
        {
            "ok": True,
            "device_name": device_name,
            "topic": topic,
            "thresholds": thresholds,
        },
    )


# ── 数据库工具 ────────────────────────────────────────────────────────────────


def _get_conn():
    return psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASS,
    )


def _db_fetch(sql: str, params: tuple) -> list:
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchall()
    finally:
        conn.close()


def _db_execute(sql: str, params: tuple) -> int:
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            count = cur.rowcount
        conn.commit()
        return count
    finally:
        conn.close()


# ── HTTP 响应工具 ─────────────────────────────────────────────────────────────


def _resp(status: int, body: dict) -> dict:
    return {
        "statusCode": status,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type",
        },
        "body": json.dumps(body),
    }
