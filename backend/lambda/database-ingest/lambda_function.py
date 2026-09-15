"""Transactional event history, retry deduplication and ordered current state."""

import hashlib
import json
import os
import psycopg2
from spill_common import event_time, integer, observed, pick


def normalize(event):
    topic = str(pick(event, "mqtt_topic", "topic") or "")
    kind = str(pick(event, "type", "event_type") or "").lower()
    if topic == "waterlevel/heartbeat" or kind == "heartbeat":
        kind = "heartbeat"
    elif topic == "rfid" or any(
        k in event for k in ("rfid_uid", "rfid_id", "rfidUid", "rfidId", "uid")
    ):
        kind = "rfid"
    else:
        kind = "sensor"
    device = str(
        pick(event, "device_id", "deviceId", "source_id", "source") or ""
    ).strip()
    if not device:
        raise ValueError("missing device_id")
    ts, at = event_time(event)
    data = {"type": kind, "device_id": device, "ts": ts, "at": at, "topic": topic}
    if kind == "sensor":
        data["sensor_id"] = integer(pick(event, "sensor_id", "sensorId"), "sensor_id")
        state = str(pick(event, "state", "status") or "").strip().upper()
        if state not in ("WET", "DRY", "DRYING"):
            raise ValueError("state must be WET, DRY or DRYING")
        data.update(state=state, wet=state == "WET")
        value = pick(event, "value", "raw")
        data["value"] = integer(value, "value") if value is not None else None
    elif kind == "rfid":
        for name, aliases in [
            ("rfid_id", ("rfid_id", "rfidId")),
            ("rfid_uid", ("rfid_uid", "rfidUid", "uid")),
        ]:
            data[name] = str(pick(event, *aliases) or "").strip()
            if not data[name]:
                raise ValueError(f"missing {name}")
        data["rfid_uid"] = data["rfid_uid"].upper()
    else:
        value = pick(event, "uptime_ms", "uptimeMs")
        data["uptime_ms"] = integer(value, "uptime_ms") if value is not None else None
    # Stable publisher IDs deduplicate even when IoT receipt times differ.
    # Without one, only messages carrying a stable timestamp can be deduplicated.
    semantic = {k: v for k, v in data.items() if k not in ("at", "ts")}
    publisher_time = pick(event, "event_ts_ms", "timestamp", "ts")
    explicit_id = event.get("event_id")
    if explicit_id is not None:
        if not isinstance(explicit_id, str) or not explicit_id.strip():
            raise ValueError("event_id must be a nonempty string")
        identity = [device, kind, explicit_id]
        if publisher_time is not None:
            semantic["ts"] = ts
    else:
        semantic["ts"] = ts
        identity = semantic
    encoded = lambda obj: json.dumps(
        obj, sort_keys=True, separators=(",", ":")
    ).encode()
    data["fingerprint"] = hashlib.sha256(encoded(semantic)).hexdigest()
    stable = (
        explicit_id is not None
        or pick(event, "event_ts_ms", "timestamp", "ts", "received_ts") is not None
    )
    data["event_key"] = (
        hashlib.sha256(encoded(identity)).hexdigest() if stable else None
    )
    return data


@observed("ingestion")
def lambda_handler(event, context):
    d = normalize(event)
    conn = psycopg2.connect(
        host=os.environ["DB_HOST"],
        port=int(os.getenv("DB_PORT", "5432")),
        dbname=os.environ["DB_NAME"],
        user=os.environ["DB_USER"],
        password=os.environ["DB_PASS"],
    )
    try:
        with conn:
            with conn.cursor() as cur:
                if d["event_key"]:
                    cur.execute(
                        "INSERT INTO ingested_events (event_key, payload_hash) VALUES (%s,%s) "
                        "ON CONFLICT DO NOTHING RETURNING event_key",
                        (d["event_key"], d["fingerprint"]),
                    )
                    if cur.fetchone() is None:
                        cur.execute(
                            "SELECT payload_hash FROM ingested_events WHERE event_key=%s",
                            (d["event_key"],),
                        )
                        if cur.fetchone()[0] != d["fingerprint"]:
                            raise ValueError("event_id reused with different data")
                        return {
                            "ok": True,
                            "duplicate": True,
                            "event_key": d["event_key"],
                            "type": d["type"],
                        }
                raw = json.dumps(event)
                if d["type"] == "sensor":
                    cur.execute(
                        "INSERT INTO waterlevel_readings "
                        "(received_at,received_ts,mqtt_topic,device_id,sensor_id,value,wet,raw) "
                        "VALUES (%s,%s,%s,%s,%s,%s,%s,%s::jsonb)",
                        (
                            d["at"],
                            d["ts"],
                            d["topic"],
                            d["device_id"],
                            d["sensor_id"],
                            d["value"],
                            d["wet"],
                            raw,
                        ),
                    )
                    cur.execute(
                        "INSERT INTO sensorstate (sensor_id,wet,state,updated_ts,updated_at,last_value,mqtt_topic,raw) "
                        "VALUES (%s,%s,%s,%s,%s,%s,%s,%s::jsonb) ON CONFLICT (sensor_id) DO UPDATE SET "
                        "wet=EXCLUDED.wet,state=EXCLUDED.state,updated_ts=EXCLUDED.updated_ts,"
                        "updated_at=EXCLUDED.updated_at,last_value=EXCLUDED.last_value,mqtt_topic=EXCLUDED.mqtt_topic,raw=EXCLUDED.raw "
                        "WHERE EXCLUDED.updated_ts > sensorstate.updated_ts",
                        (
                            d["sensor_id"],
                            d["wet"],
                            d["state"],
                            d["ts"],
                            d["at"],
                            d["value"],
                            d["topic"],
                            raw,
                        ),
                    )
                elif d["type"] == "heartbeat":
                    cur.execute(
                        "INSERT INTO device_heartbeats (device_id,last_seen_at,last_seen_ts,mqtt_topic,uptime_ms,raw) "
                        "VALUES (%s,%s,%s,%s,%s,%s::jsonb) ON CONFLICT (device_id) DO UPDATE SET "
                        "last_seen_at=EXCLUDED.last_seen_at,last_seen_ts=EXCLUDED.last_seen_ts,"
                        "mqtt_topic=EXCLUDED.mqtt_topic,uptime_ms=EXCLUDED.uptime_ms,raw=EXCLUDED.raw "
                        "WHERE EXCLUDED.last_seen_ts > device_heartbeats.last_seen_ts",
                        (
                            d["device_id"],
                            d["at"],
                            d["ts"],
                            d["topic"],
                            d["uptime_ms"],
                            raw,
                        ),
                    )
                else:
                    cur.execute(
                        "INSERT INTO rfid_scans (device_id,rfid_id,rfid_uid,scan_timestamp,scanned_at,mqtt_topic,raw) "
                        "VALUES (%s,%s,%s,%s,%s,%s,%s::jsonb)",
                        (
                            d["device_id"],
                            d["rfid_id"],
                            d["rfid_uid"],
                            d["ts"] // 1000,
                            d["at"],
                            d["topic"],
                            raw,
                        ),
                    )
                updated = cur.rowcount > 0
        return {
            "ok": True,
            "type": d["type"],
            "duplicate": False,
            "current_state_updated": updated,
            "event_key": d["event_key"],
            "deduplication_available": d["event_key"] is not None,
        }
    finally:
        conn.close()
