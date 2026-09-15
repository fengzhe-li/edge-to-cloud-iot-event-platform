from spill_common import observed
import os
import json
import pg8000
from datetime import datetime, timezone

DB_HOST = os.environ["DB_HOST"]
DB_PORT = int(os.environ.get("DB_PORT", "5432"))
DB_NAME = os.environ["DB_NAME"]
DB_USER = os.environ["DB_USER"]
DB_PASS = os.environ["DB_PASS"]

SENSORSTATE_TABLE = os.environ.get("SENSORSTATE_TABLE", "sensorstate")
RFID_TABLE = os.environ.get("RFID_TABLE", "rfid_scans")
HEARTBEAT_TABLE = os.environ.get("HEARTBEAT_TABLE", "device_heartbeats")
HEARTBEAT_TIMEOUT_SECONDS = int(os.environ.get("HEARTBEAT_TIMEOUT_SECONDS", "60"))


def _resp(code, obj):
    return {
        "statusCode": code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Content-Type",
            "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
        },
        "body": json.dumps(obj, default=str),
    }


def _calc_age_seconds(last_seen_ts, last_seen_at):
    now_utc = datetime.now(timezone.utc)

    if last_seen_ts is not None:
        try:
            now_ms = int(now_utc.timestamp() * 1000)
            return max(0, (now_ms - int(last_seen_ts)) / 1000.0)
        except Exception:
            pass

    if last_seen_at is not None:
        try:
            if getattr(last_seen_at, "tzinfo", None) is None:
                last_seen_at = last_seen_at.replace(tzinfo=timezone.utc)
            return max(0, (now_utc - last_seen_at).total_seconds())
        except Exception:
            pass

    return None


def _build_system_obj(
    device_id, last_seen_at, last_seen_ts, mqtt_topic, uptime_ms, raw
):
    age_seconds = _calc_age_seconds(last_seen_ts, last_seen_at)
    is_online = age_seconds is not None and age_seconds <= HEARTBEAT_TIMEOUT_SECONDS

    return {
        "heartbeat_found": True,
        "online": is_online,
        "status": "online" if is_online else "offline",
        "device_id": device_id,
        "last_seen_ts": str(last_seen_ts) if last_seen_ts is not None else None,
        "last_seen_at": str(last_seen_at) if last_seen_at is not None else None,
        "age_seconds": round(age_seconds, 2) if age_seconds is not None else None,
        "timeout_seconds": HEARTBEAT_TIMEOUT_SECONDS,
        "mqtt_topic": mqtt_topic,
        "uptime_ms": uptime_ms,
        "raw": raw,
    }


@observed("status_api", api=True)
def lambda_handler(event, context):
    conn = None
    try:
        method = (
            event.get("requestContext", {}).get("http", {}).get("method")
            or event.get("httpMethod")
            or "GET"
        )

        if method == "OPTIONS":
            return _resp(200, {"ok": True})

        if method != "GET":
            return _resp(405, {"ok": False, "error": "Method not allowed"})

        qs = event.get("queryStringParameters") or {}

        sensor_id = qs.get("sensor_id")
        rfid_uid = qs.get("rfid_uid") or qs.get("rfid_tag")
        rfid_id = qs.get("rfid_id")
        device_id = qs.get("device_id")

        if rfid_uid:
            rfid_uid = str(rfid_uid).strip().upper()

        conn = pg8000.connect(
            host=DB_HOST, port=DB_PORT, database=DB_NAME, user=DB_USER, password=DB_PASS
        )

        cursor = conn.cursor()
        result = {"ok": True}

        # ---------------------------------------------------
        # 0. heartbeat / system 状态
        # - 传了 device_id: 只查一个设备
        # - 没传 device_id: 一次性返回所有设备最新状态
        #
        # 用 DISTINCT ON (device_id) 是为了防止未来一台设备有多条 heartbeat 历史记录
        # ---------------------------------------------------
        # ---------------------------------------------------

        if device_id:
            cursor.execute(
                f"""
                SELECT DISTINCT ON (device_id)
                    device_id, last_seen_at, last_seen_ts, mqtt_topic, uptime_ms, raw
                FROM {HEARTBEAT_TABLE}
                WHERE device_id = %s
                ORDER BY device_id, last_seen_ts DESC NULLS LAST, last_seen_at DESC NULLS LAST;
                """,
                (device_id,),
            )
            heartbeat_row = cursor.fetchone()

            if heartbeat_row:
                (
                    hb_device_id,
                    last_seen_at,
                    last_seen_ts,
                    hb_mqtt_topic,
                    uptime_ms,
                    hb_raw,
                ) = heartbeat_row
                result["system"] = _build_system_obj(
                    hb_device_id,
                    last_seen_at,
                    last_seen_ts,
                    hb_mqtt_topic,
                    uptime_ms,
                    hb_raw,
                )
            else:
                result["system"] = {
                    "heartbeat_found": False,
                    "online": False,
                    "status": "offline",
                    "device_id": device_id,
                    "last_seen_ts": None,
                    "last_seen_at": None,
                    "age_seconds": None,
                    "timeout_seconds": HEARTBEAT_TIMEOUT_SECONDS,
                    "mqtt_topic": None,
                    "uptime_ms": None,
                    "raw": None,
                }

        else:
            cursor.execute(
                f"""
                SELECT DISTINCT ON (device_id)
                    device_id, last_seen_at, last_seen_ts, mqtt_topic, uptime_ms, raw
                FROM {HEARTBEAT_TABLE}
                ORDER BY device_id, last_seen_ts DESC NULLS LAST, last_seen_at DESC NULLS LAST;
                """
            )
            heartbeat_rows = cursor.fetchall()

            systems = []
            for row in heartbeat_rows:
                (
                    hb_device_id,
                    last_seen_at,
                    last_seen_ts,
                    hb_mqtt_topic,
                    uptime_ms,
                    hb_raw,
                ) = row
                systems.append(
                    _build_system_obj(
                        hb_device_id,
                        last_seen_at,
                        last_seen_ts,
                        hb_mqtt_topic,
                        uptime_ms,
                        hb_raw,
                    )
                )

            result["systems"] = systems
            result["system_count"] = len(systems)

        # 1. 查询 sensor 状态（可选）
        if sensor_id:
            cursor.execute(
                f"""
                SELECT sensor_id, wet, updated_ts, state, updated_at, last_value, mqtt_topic, raw
                FROM {SENSORSTATE_TABLE}
                WHERE sensor_id = %s
                LIMIT 1;
                """,
                (sensor_id,),
            )
            row = cursor.fetchone()

            if row:
                (
                    db_sensor_id,
                    wet,
                    updated_ts,
                    state,
                    updated_at,
                    last_value,
                    mqtt_topic,
                    raw,
                ) = row
                status_val = (
                    str(state).strip().lower()
                    if state
                    else ("wet" if bool(wet) else "dry")
                )

                result["sensor"] = {
                    "found": True,
                    "sensor_id": db_sensor_id,
                    "status": status_val,
                    "wet": wet,
                    "state": state,
                    "updated_ts": str(updated_ts) if updated_ts is not None else None,
                    "updated_at": str(updated_at) if updated_at is not None else None,
                    "last_value": last_value,
                    "mqtt_topic": mqtt_topic,
                    "raw": raw,
                }
            else:
                result["sensor"] = {
                    "found": False,
                    "sensor_id": sensor_id,
                    "status": "unknown",
                    "wet": None,
                    "state": None,
                    "updated_ts": None,
                    "updated_at": None,
                    "last_value": None,
                    "mqtt_topic": None,
                    "raw": None,
                }

        # 2. 查询 RFID 最新记录（可选）
        if rfid_uid or rfid_id or device_id:
            conditions = []
            params = []

            if rfid_uid:
                conditions.append("rfid_uid = %s")
                params.append(rfid_uid)

            if rfid_id:
                conditions.append("rfid_id = %s")
                params.append(rfid_id)

            if device_id:
                conditions.append("device_id = %s")
                params.append(device_id)

            where_sql = " AND ".join(conditions)

            cursor.execute(
                f"""
                SELECT device_id, rfid_id, rfid_uid, scan_timestamp, scanned_at, mqtt_topic, raw
                FROM {RFID_TABLE}
                WHERE {where_sql}
                ORDER BY scan_timestamp DESC
                LIMIT 1;
                """,
                tuple(params),
            )
            rfid_row = cursor.fetchone()

            if rfid_row:
                (
                    db_device_id,
                    db_rfid_id,
                    db_rfid_uid,
                    scan_timestamp,
                    scanned_at,
                    mqtt_topic,
                    raw,
                ) = rfid_row
                result["rfid"] = {
                    "found": True,
                    "device_id": db_device_id,
                    "rfid_id": db_rfid_id,
                    "rfid_uid": db_rfid_uid,
                    "scan_timestamp": scan_timestamp,
                    "scanned_at": str(scanned_at) if scanned_at is not None else None,
                    "mqtt_topic": mqtt_topic,
                    "raw": raw,
                }
            else:
                result["rfid"] = {
                    "found": False,
                    "device_id": device_id,
                    "rfid_id": rfid_id,
                    "rfid_uid": rfid_uid,
                }

        return _resp(200, result)

    except Exception:
        raise

    finally:
        if conn:
            conn.close()
