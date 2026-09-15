"""Read-only operational summaries over existing tables; no inferred staff joins."""

import json
import os
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone

import psycopg2
from psycopg2.extras import RealDictCursor
from spill_common import observed, response

MAX_WINDOW = timedelta(days=31)
MAX_READINGS = 10000


def parse_window(params, now):
    def instant(value):
        try:
            result = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if result.tzinfo is None:
                raise ValueError()
            return result.astimezone(timezone.utc)
        except (ValueError, TypeError, AttributeError):
            raise ValueError(
                "start/end must be ISO-8601 timestamps with timezone"
            ) from None

    if "start" in params or "end" in params:
        if (
            set(params) - {"start", "end"}
            or not params.get("start")
            or not params.get("end")
        ):
            raise ValueError("provide both start and end, without window_hours")
        start, end = instant(params["start"]), instant(params["end"])
    else:
        if set(params) - {"window_hours"}:
            raise ValueError("unknown query parameter")
        try:
            hours = float(params.get("window_hours", 24))
            if not 0 < hours <= 744:
                raise ValueError()
            end = now
            start = end - timedelta(hours=hours)
        except (ValueError, TypeError, OverflowError):
            raise ValueError(
                "window_hours must be greater than 0 and at most 744"
            ) from None
    if not timedelta(0) < end - start <= MAX_WINDOW or end > now:
        raise ValueError(
            "window must be positive, at most 31 days and not in the future"
        )
    return start, end


def device_health(
    heartbeats, latest_readings, configured_devices, now_ms, timeout_ms=60000
):
    beats = {row["device_id"]: row for row in heartbeats}
    readings = {row["device_id"]: row["last_sensor_ts"] for row in latest_readings}
    devices = sorted(set(beats) | set(readings) | set(configured_devices))
    result = []
    for device in devices:
        hb = beats.get(device, {})
        ts = hb.get("last_seen_ts")
        age = now_ms - int(ts) if ts is not None else None
        online = age is not None and 0 <= age <= timeout_ms
        status = (
            "unknown" if age is None or age < 0 else ("online" if online else "offline")
        )
        reading_ts = readings.get(device)
        quiet = online and (reading_ts is None or now_ms - int(reading_ts) > timeout_ms)
        uptime = hb.get("uptime_ms")
        result.append(
            {
                "device_id": device,
                "status": status,
                "quiet_but_online": quiet,
                "last_seen_at": hb.get("last_seen_at"),
                "last_seen_ts": ts,
                "heartbeat_age_seconds": age / 1000
                if age is not None and age >= 0
                else None,
                "last_sensor_ts": reading_ts,
                "reported_uptime_seconds": uptime / 1000
                if uptime is not None and uptime >= 0
                else None,
                "availability_percent": None,
            }
        )
    return result


def reading_state(row):
    if row["wet"] is True:
        return "WET"
    raw = row.get("raw") or {}
    state = (
        str(raw.get("state", raw.get("status", ""))).strip().upper()
        if isinstance(raw, dict)
        else ""
    )
    if row["wet"] is False:
        return "DRYING" if state == "DRYING" else "DRY"
    return "UNKNOWN"


def incident_summary(readings, start_ms, end_ms, zone_map):
    grouped = defaultdict(list)
    for row in readings:
        grouped[(row["device_id"], row["sensor_id"])].append(row)
    transitions, incidents, first_wet = [], [], []
    ambiguous_count = 0
    for (device, sensor), rows in grouped.items():
        rows.sort(key=lambda row: (row["received_ts"], row["id"]))
        states_by_time = defaultdict(set)
        for row in rows:
            states_by_time[row["received_ts"]].add(reading_state(row))
        previous = None
        for row in rows:
            ts, state = row["received_ts"], reading_state(row)
            ambiguous = len(states_by_time[ts]) > 1
            if start_ms <= ts < end_ms:
                ambiguous_count += int(ambiguous)
                if previous is None or state != previous["state"] or ambiguous:
                    item = {
                        "record_id": row["id"],
                        "device_id": device,
                        "sensor_id": sensor,
                        "zone_id": zone_map.get(str(sensor)),
                        "timestamp_ms": ts,
                        "from_state": previous["state"] if previous else None,
                        "to_state": state,
                        "ambiguous_timestamp": ambiguous
                        or bool(previous and previous["ambiguous"]),
                    }
                    transitions.append(item)
                    if state == "WET" and not item["ambiguous_timestamp"]:
                        if previous and previous["state"] in ("DRY", "DRYING"):
                            incidents.append(
                                {**item, "classification": "observed_wet_transition"}
                            )
                        elif previous is None or previous["state"] == "UNKNOWN":
                            first_wet.append(
                                {
                                    **item,
                                    "classification": "first_observed_wet_onset_unknown",
                                }
                            )
            previous = {"state": state, "ambiguous": ambiguous}

    def counts(key):
        return dict(
            sorted(
                Counter(
                    str(row[key]) if row[key] is not None else "unmapped"
                    for row in incidents
                ).items()
            )
        )

    recent = sorted(
        incidents + first_wet,
        key=lambda x: (x["timestamp_ms"], x["record_id"]),
        reverse=True,
    )
    transitions.sort(key=lambda x: (x["timestamp_ms"], x["record_id"]), reverse=True)
    return {
        "incident_count": len(incidents),
        "first_observed_wet_count": len(first_wet),
        "events_per_hour": len(incidents) / ((end_ms - start_ms) / 3600000),
        "by_sensor": counts("sensor_id"),
        "by_device": counts("device_id"),
        "by_zone": counts("zone_id"),
        "recent_incidents": recent[:20],
        "recent_incidents_total": len(recent),
        "state_transitions": transitions[:50],
        "state_transitions_total": len(transitions),
        "ambiguous_reading_count": ambiguous_count,
    }


# Include the complete final pre-window timestamp group for each sensor. This
# prevents both boundary false incidents and arbitrary tie-state interpretation.
READINGS_SQL = """
WITH prior AS (
 SELECT device_id,sensor_id,max(received_ts) AS ts FROM waterlevel_readings
 WHERE received_ts < %s GROUP BY device_id,sensor_id
), selected AS (
 SELECT r.* FROM waterlevel_readings r JOIN prior p
 ON r.device_id=p.device_id AND r.sensor_id=p.sensor_id AND r.received_ts=p.ts
 UNION ALL
 SELECT * FROM waterlevel_readings WHERE received_ts >= %s AND received_ts < %s
)
SELECT id,device_id,sensor_id,received_ts,wet,raw FROM selected LIMIT %s
"""


def load_data(conn, start_ms, end_ms, now_ms):
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(READINGS_SQL, (start_ms, start_ms, end_ms, MAX_READINGS + 1))
        readings = list(cur.fetchall())
        if len(readings) > MAX_READINGS:
            return None

        def rows(sql, params=()):
            cur.execute(sql, params)
            return list(cur.fetchall())

        return {
            "readings": readings,
            "heartbeats": rows(
                "SELECT device_id,last_seen_at,last_seen_ts,uptime_ms FROM device_heartbeats"
            ),
            "latest_readings": rows(
                "SELECT device_id,max(received_ts) AS last_sensor_ts FROM waterlevel_readings WHERE received_ts <= %s GROUP BY device_id",
                (now_ms,),
            ),
            "configuration": rows(
                "SELECT device_id,sensor_id,active,updated_at AS stored_updated_at FROM sensor_config ORDER BY device_id,sensor_id"
            ),
            "thresholds": rows(
                "SELECT device_name,sensor_id,threshold_value,updated_at AS stored_updated_at FROM sensor_thresholds ORDER BY device_name,sensor_id"
            ),
            "current_sensor_state": rows(
                "SELECT sensor_id,state,updated_ts FROM sensorstate ORDER BY sensor_id"
            ),
            "rfid": rows(
                "SELECT count(*) AS scan_count FROM rfid_scans WHERE scanned_at >= to_timestamp(%s/1000.0) AND scanned_at < to_timestamp(%s/1000.0)",
                (start_ms, end_ms),
            )[0],
            # Legacy rows have no sensor key and timezone-naive dates. Surface
            # separately without merging or assigning invented timezone semantics.
            "legacy_spill_records": rows(
                "SELECT s.id,s.device_id,d.zone_id,s.status,s.detected_at FROM spill_events s LEFT JOIN devices d ON d.id=s.device_id ORDER BY s.id DESC LIMIT 20"
            ),
        }


@observed("analytics", api=True)
def lambda_handler(event, context):
    method = event.get("httpMethod") or event.get("requestContext", {}).get(
        "http", {}
    ).get("method", "GET")
    if method != "GET":
        return response(405, {"ok": False, "error": "Method not allowed"})
    if (event.get("path") or "/analytics/summary") != "/analytics/summary":
        return response(404, {"ok": False, "error": "Unknown route"})
    now = datetime.now(timezone.utc)
    start, end = parse_window(event.get("queryStringParameters") or {}, now)
    start_ms, end_ms, now_ms = (int(t.timestamp() * 1000) for t in (start, end, now))
    if end_ms <= start_ms:
        raise ValueError("window must be at least one millisecond")
    zone_map = json.loads(os.getenv("SENSOR_ZONE_MAP", "{}"))
    if not isinstance(zone_map, dict):
        raise RuntimeError("SENSOR_ZONE_MAP must be an object")
    conn = psycopg2.connect(
        host=os.environ["DB_HOST"],
        port=int(os.getenv("DB_PORT", "5432")),
        dbname=os.environ["DB_NAME"],
        user=os.environ["DB_USER"],
        password=os.environ["DB_PASS"],
    )
    try:
        conn.set_session(readonly=True, isolation_level="REPEATABLE READ")
        with conn:
            with conn.cursor() as cur:
                cur.execute("SET LOCAL statement_timeout = '5000ms'")
            data = load_data(conn, start_ms, end_ms, now_ms)
        if data is None:
            return response(
                422,
                {
                    "ok": False,
                    "error": "Window exceeds 10000 readings including boundary context; request a smaller window",
                },
            )
    finally:
        conn.close()
    devices = device_health(
        data["heartbeats"],
        data["latest_readings"],
        [r["device_id"] for r in data["configuration"]],
        now_ms,
        int(os.getenv("HEARTBEAT_TIMEOUT_SECONDS", "60")) * 1000,
    )
    return response(
        200,
        {
            "ok": True,
            "generated_at": now.isoformat(),
            "window": {
                "start": start.isoformat(),
                "end": end.isoformat(),
                "boundary": "start inclusive, end exclusive",
            },
            "devices": devices,
            "online_device_count": sum(d["status"] == "online" for d in devices),
            "device_count": len(devices),
            "health_as_of": "generated_at, not selected window",
            "availability": {
                "supported": False,
                "percent": None,
                "reason": "Only latest heartbeat is retained; uptime is a device-reported counter, not historical availability.",
            },
            "incidents": incident_summary(data["readings"], start_ms, end_ms, zone_map),
            "zone_mapping": {
                "source": "current configured sensor-to-zone map; not historical location",
                "mapping": zone_map,
            },
            "response_times": {
                "supported": False,
                "mean_seconds": None,
                "rfid_scans_in_window": data["rfid"]["scan_count"],
                "reason": "RFID scans have no reliable incident or acknowledgement key; proximity is not correlation.",
            },
            "current_sensor_state": data["current_sensor_state"],
            "configuration": data["configuration"],
            "thresholds": data["thresholds"],
            "configuration_history": {
                "supported": False,
                "reason": "Only current values are stored. No audit log is collected.",
            },
            "legacy_spill_records": data["legacy_spill_records"],
            "legacy_spill_note": "Latest 20 rows by ID, outside the window statistics; no sensor key and timezone-naive detected_at. Not merged with reading-derived incidents.",
        },
    )
