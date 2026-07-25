import os
import json
import psycopg2
import traceback
from datetime import datetime, timezone

# ---- DB ENV ----
DB_HOST = os.environ["DB_HOST"]
DB_PORT = int(os.environ.get("DB_PORT", "5432"))
DB_NAME = os.environ["DB_NAME"]
DB_USER = os.environ["DB_USER"]
DB_PASS = os.environ["DB_PASS"]

# ---- Tables ----
HISTORY_TABLE = os.environ.get("HISTORY_TABLE", "waterlevel_readings")
SENSORSTATE_TABLE = os.environ.get("SENSORSTATE_TABLE", "sensorstate")
RFID_TABLE = os.environ.get("RFID_TABLE", "rfid_scans")
HEARTBEAT_TABLE = os.environ.get("HEARTBEAT_TABLE", "device_heartbeats")


def log(level: str, msg: str, **kwargs):
    payload = {
        "level": level.upper(),
        "msg": msg,
        "ts": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }
    if kwargs:
        payload.update(kwargs)
    print(json.dumps(payload, default=str))


def _derive_state_and_wet(event: dict):
    """
    Accepts: WET / DRY / DRYING
    wet boolean: True only for WET, False otherwise
    """
    st = event.get("state")
    if st is None:
        return None, None
    state_str = str(st).strip().upper()
    if state_str not in {"WET", "DRY", "DRYING"}:
        return None, None
    wet = (state_str == "WET")
    return state_str, wet


def _pick_field(event: dict, *keys):
    """Return first present key value, preserving falsy values like 0."""
    for k in keys:
        if k in event:
            return event[k]
    return None


def _is_rfid_event(event: dict, mqtt_topic: str):
    return (
        mqtt_topic == "rfid"
        or any(k in event for k in ("rfid_uid", "rfid_id"))
    )


def _is_heartbeat_event(event: dict, mqtt_topic: str):
    event_type = str(_pick_field(event, "type", "event_type") or "").strip().lower()
    return (
        mqtt_topic == "waterlevel/heartbeat"
        or event_type == "heartbeat"
    )


def lambda_handler(event, context):
    # ---- Log invocation ----
    try:
        raw_str = json.dumps(event, default=str)
        log(
            "INFO",
            "Lambda invoked",
            request_id=getattr(context, "aws_request_id", None),
            event_size=len(raw_str),
            event_preview=raw_str[:2000],
        )
    except Exception:
        print("INFO Lambda invoked (failed to json-dump event)")

    # ---- Extract fields from IoT message ----
    mqtt_topic = _pick_field(event, "mqtt_topic", "topic") or ""
    received_ts = _pick_field(event, "received_ts")
    if received_ts is None:
        received_ts = int(datetime.now(timezone.utc).timestamp() * 1000)

    received_at = datetime.fromtimestamp(received_ts / 1000, tz=timezone.utc)

    device_id = (
        _pick_field(event, "deviceId", "device_id", "source_id")
        or "UNKNOWN_DEVICE"
    )

    # Preserve 0 for sensorId
    sensor_id_raw = _pick_field(event, "sensorId", "sensor_id")
    try:
        sensor_id = int(sensor_id_raw) if sensor_id_raw is not None else None
    except Exception:
        sensor_id = None

    # Numeric reading from Arduino payload ("raw"), keep 0 if present
    value = _pick_field(event, "value", "raw")

    state_str, wet = _derive_state_and_wet(event)

    log(
        "INFO",
        "Parsed fields",
        history_table=HISTORY_TABLE,
        sensorstate_table=SENSORSTATE_TABLE,
        rfid_table=RFID_TABLE,
        heartbeat_table=HEARTBEAT_TABLE,
        mqtt_topic=mqtt_topic,
        device_id=device_id,
        sensor_id=sensor_id,
        state=state_str,
        wet=wet,
        received_ts=received_ts,
        received_at=received_at.isoformat(),
        value=value,
    )

    is_rfid_event = _is_rfid_event(event, mqtt_topic)
    is_heartbeat_event = _is_heartbeat_event(event, mqtt_topic)
    log(
        "INFO",
        "Event classification",
        is_rfid_event=is_rfid_event,
        is_heartbeat_event=is_heartbeat_event,
        mqtt_topic=mqtt_topic,
        has_rfid_id=("rfid_id" in event or "rfidId" in event),
        has_rfid_uid=("rfid_uid" in event or "rfidUid" in event or "uid" in event),
    )

    # ---- Validate ----
    if not is_rfid_event and not is_heartbeat_event and sensor_id is None:
        log("ERROR", "Missing/invalid sensor_id", sensor_id_raw=sensor_id_raw)
        return {"ok": False, "error": "missing/invalid sensor_id"}

    if not is_rfid_event and not is_heartbeat_event and (state_str is None or wet is None):
        log("WARN", "Skipping: invalid/missing state", state=event.get("state"))
        return {"ok": True, "skipped": True, "reason": "invalid/missing state"}

    conn = None
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASS,
        )
        log("INFO", "DB connection established", host=DB_HOST, db=DB_NAME, port=DB_PORT)

        with conn:
            with conn.cursor() as cur:
                if is_heartbeat_event:
                    source = _pick_field(event, "source", "deviceId", "device_id", "source_id")
                    heartbeat_device_id = str(source or device_id or "").strip() or "UNKNOWN_DEVICE"
                    uptime_ms = _pick_field(event, "uptime_ms", "uptimeMs")

                    if heartbeat_device_id == "UNKNOWN_DEVICE":
                        log("ERROR", "Missing heartbeat device_id", event=event)
                        return {"ok": False, "error": "missing heartbeat device_id"}

                    cur.execute(
                        f"""
                        INSERT INTO {HEARTBEAT_TABLE}
                          (device_id, last_seen_at, last_seen_ts, mqtt_topic, uptime_ms, raw)
                        VALUES
                          (%s, %s, %s, %s, %s, %s::jsonb)
                        ON CONFLICT (device_id) DO UPDATE SET
                          last_seen_at = EXCLUDED.last_seen_at,
                          last_seen_ts = EXCLUDED.last_seen_ts,
                          mqtt_topic   = EXCLUDED.mqtt_topic,
                          uptime_ms    = EXCLUDED.uptime_ms,
                          raw          = EXCLUDED.raw
                        """,
                        (
                            heartbeat_device_id,
                            received_at,
                            received_ts,
                            mqtt_topic,
                            uptime_ms,
                            json.dumps(event),
                        ),
                    )
                    log(
                        "INFO",
                        "Upserted heartbeat row",
                        table=HEARTBEAT_TABLE,
                        device_id=heartbeat_device_id,
                        received_ts=received_ts,
                        received_at=received_at.isoformat(),
                        uptime_ms=uptime_ms,
                    )
                    return {
                        "ok": True,
                        "type": "heartbeat",
                        "device_id": heartbeat_device_id,
                        "received_ts": received_ts,
                    }

                if is_rfid_event:
                    rfid_id = _pick_field(event, "rfid_id", "rfidId")
                    rfid_uid = _pick_field(event, "rfid_uid", "rfidUid", "uid")
                    scan_ts_raw = _pick_field(event, "timestamp", "scan_timestamp", "ts")
                    log(
                        "INFO",
                        "RFID fields extracted",
                        device_id=device_id,
                        rfid_id=rfid_id,
                        rfid_uid=rfid_uid,
                        scan_ts_raw=scan_ts_raw,
                        mqtt_topic=mqtt_topic,
                    )

                    if not device_id or device_id == "UNKNOWN_DEVICE":
                        log("ERROR", "Missing RFID device_id", event=event)
                        return {"ok": False, "error": "missing device_id"}

                    if not rfid_id:
                        log("ERROR", "Missing RFID rfid_id", event=event)
                        return {"ok": False, "error": "missing rfid_id"}

                    if not rfid_uid:
                        log("ERROR", "Missing RFID rfid_uid", event=event)
                        return {"ok": False, "error": "missing rfid_uid"}

                    try:
                        scan_timestamp = int(scan_ts_raw) if scan_ts_raw is not None else received_ts
                    except Exception:
                        log("ERROR", "Invalid RFID timestamp", scan_ts_raw=scan_ts_raw)
                        return {"ok": False, "error": "invalid timestamp"}

                    # Arduino publishes RFID timestamps in epoch seconds.
                    if scan_timestamp < 10_000_000_000:
                        scanned_at = datetime.fromtimestamp(scan_timestamp, tz=timezone.utc)
                    else:
                        scanned_at = datetime.fromtimestamp(scan_timestamp / 1000, tz=timezone.utc)
                    normalized_uid = str(rfid_uid).strip().upper()
                    log(
                        "INFO",
                        "RFID values normalized",
                        device_id=device_id,
                        rfid_id=rfid_id,
                        rfid_uid=normalized_uid,
                        scan_timestamp=scan_timestamp,
                        scanned_at=scanned_at.isoformat(),
                        mqtt_topic=mqtt_topic,
                    )

                    log(
                        "INFO",
                        "Attempting RFID insert",
                        table=RFID_TABLE,
                        device_id=device_id,
                        rfid_id=rfid_id,
                        rfid_uid=normalized_uid,
                        scan_timestamp=scan_timestamp,
                    )
                    cur.execute(
                        f"""
                        INSERT INTO {RFID_TABLE}
                          (device_id, rfid_id, rfid_uid, scan_timestamp, scanned_at, mqtt_topic, raw)
                        VALUES
                          (%s, %s, %s, %s, %s, %s, %s::jsonb)
                        """,
                        (
                            device_id,
                            rfid_id,
                            normalized_uid,
                            scan_timestamp,
                            scanned_at,
                            mqtt_topic,
                            json.dumps(event),
                        ),
                    )
                    log(
                        "INFO",
                        "Inserted RFID row",
                        table=RFID_TABLE,
                        device_id=device_id,
                        rfid_id=rfid_id,
                        rfid_uid=normalized_uid,
                        scan_timestamp=scan_timestamp,
                    )
                    return {
                        "ok": True,
                        "type": "rfid",
                        "device_id": device_id,
                        "rfid_id": rfid_id,
                        "rfid_uid": normalized_uid,
                    }

                # 1) Insert into HISTORY table (store every event you receive)
                cur.execute(
                    f"""
                    INSERT INTO {HISTORY_TABLE}
                      (received_at, received_ts, mqtt_topic, device_id, sensor_id, value, wet, raw)
                    VALUES
                      (%s, %s, %s, %s, %s, %s, %s, %s::jsonb)
                    """,
                    (
                        received_at,
                        received_ts,
                        mqtt_topic,
                        device_id,
                        sensor_id,
                        value,
                        wet,
                        json.dumps(event),
                    ),
                )
                log("INFO", "Inserted history row", table=HISTORY_TABLE, sensor_id=sensor_id, state=state_str)

                # 2) UPSERT latest snapshot into SENSORSTATE table
                cur.execute(
                    f"""
                    INSERT INTO {SENSORSTATE_TABLE}
                      (sensor_id, wet, state, updated_ts, updated_at, last_value, mqtt_topic, raw)
                    VALUES
                      (%s, %s, %s, %s, %s, %s, %s, %s::jsonb)
                    ON CONFLICT (sensor_id) DO UPDATE SET
                      wet        = EXCLUDED.wet,
                      state      = EXCLUDED.state,
                      updated_ts = EXCLUDED.updated_ts,
                      updated_at = EXCLUDED.updated_at,
                      last_value = EXCLUDED.last_value,
                      mqtt_topic = EXCLUDED.mqtt_topic,
                      raw        = EXCLUDED.raw
                    """,
                    (
                        sensor_id,
                        wet,
                        state_str,
                        received_ts,
                        received_at,
                        value,
                        mqtt_topic,
                        json.dumps(event),
                    ),
                )
                log("INFO", "Upserted snapshot", table=SENSORSTATE_TABLE, sensor_id=sensor_id, state=state_str)

        return {"ok": True, "sensor_id": sensor_id, "state": state_str, "wet": wet}

    except Exception as e:
        log("ERROR", "Lambda failed", error=str(e), traceback=traceback.format_exc())
        raise

    finally:
        if conn is not None:
            try:
                conn.close()
                log("INFO", "DB connection closed")
            except Exception:
                print("WARN could not close DB connection")
