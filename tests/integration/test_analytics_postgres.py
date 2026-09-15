"""Analytics SQL verified using the existing disposable-PostgreSQL CI service."""

import json
import os
import uuid
from pathlib import Path

import psycopg2
import pytest

pytestmark = pytest.mark.postgres


@pytest.fixture
def analytics_db(loader, monkeypatch):
    url = os.getenv("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL not set")
    original = psycopg2.connect
    conn = original(url)
    conn.autocommit = True
    schema = "analytics_" + uuid.uuid4().hex
    with conn.cursor() as cur:
        cur.execute(f"CREATE SCHEMA {schema}")
        cur.execute(
            Path("backend/database/schema.sql")
            .read_text()
            .replace("public.", schema + ".")
        )
        cur.execute(f"SET search_path TO {schema}")
    module = loader("analytics")

    def connect(**kwargs):
        c = original(url)
        with c.cursor() as cur:
            cur.execute(f"SET search_path TO {schema}")
        c.commit()
        return c

    monkeypatch.setattr(module.psycopg2, "connect", connect)
    try:
        yield module, conn
    finally:
        with conn.cursor() as cur:
            cur.execute(f"DROP SCHEMA {schema} CASCADE")
        conn.close()


def insert(conn, ts, wet, sensor=0, device="A"):
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO waterlevel_readings (received_at,received_ts,mqtt_topic,device_id,sensor_id,wet,raw) "
            "VALUES (to_timestamp(%s/1000.0),%s,'sensor',%s,%s,%s,%s::jsonb)",
            (
                ts,
                ts,
                device,
                sensor,
                wet,
                json.dumps({"state": "WET" if wet else "DRY"}),
            ),
        )


def test_boundary_context_and_exclusive_end(analytics_db):
    m, c = analytics_db
    for ts, wet in [(0, False), (1000, True), (2000, True), (3000, False)]:
        insert(c, ts, wet)
    data = m.load_data(c, 1000, 3000, 10000)
    assert sorted(r["received_ts"] for r in data["readings"]) == [0, 1000, 2000]
    result = m.incident_summary(data["readings"], 1000, 3000, {"0": 1})
    assert result["incident_count"] == 1 and result["by_zone"] == {"1": 1}


def test_wet_before_window_is_not_new_incident(analytics_db):
    m, c = analytics_db
    insert(c, 0, True)
    insert(c, 2000, True)
    data = m.load_data(c, 1000, 3000, 10000)
    result = m.incident_summary(data["readings"], 1000, 3000, {})
    assert result["incident_count"] == 0 and result["first_observed_wet_count"] == 0


def test_boundary_conflict_is_preserved(analytics_db):
    m, c = analytics_db
    insert(c, 0, True)
    insert(c, 0, False)
    insert(c, 2000, True)
    data = m.load_data(c, 1000, 3000, 10000)
    assert len(data["readings"]) == 3
    result = m.incident_summary(data["readings"], 1000, 3000, {})
    assert result["incident_count"] == 0
    assert result["state_transitions"][0]["ambiguous_timestamp"]


def test_rfid_window_and_current_settings(analytics_db):
    m, c = analytics_db
    with c.cursor() as cur:
        for ts in [0, 1, 2, 3]:
            cur.execute(
                "INSERT INTO rfid_scans (device_id,rfid_id,rfid_uid,scan_timestamp,scanned_at,mqtt_topic,raw) VALUES ('A','r','tag',%s,to_timestamp(%s),'rfid','{}')",
                (ts, ts),
            )
        cur.execute(
            "INSERT INTO sensor_config (device_id,sensor_id,active) VALUES ('A',0,false)"
        )
        cur.execute(
            "INSERT INTO sensor_thresholds (device_name,sensor_id,threshold_value) VALUES ('A',0,500)"
        )
    data = m.load_data(c, 1000, 3000, 10000)
    assert data["rfid"]["scan_count"] == 2
    assert data["configuration"][0]["active"] is False
    assert data["thresholds"][0]["threshold_value"] == 500


def test_api_readonly_real_database(analytics_db, ctx, monkeypatch):
    m, c = analytics_db
    insert(c, 0, False)
    insert(c, 2000, True)
    monkeypatch.setenv("SENSOR_ZONE_MAP", '{"0":1}')
    result = m.lambda_handler(
        {
            "path": "/analytics/summary",
            "httpMethod": "GET",
            "queryStringParameters": {
                "start": "1970-01-01T00:00:01Z",
                "end": "1970-01-01T00:00:03Z",
            },
        },
        ctx,
    )
    body = json.loads(result["body"])
    assert result["statusCode"] == 200 and body["incidents"]["incident_count"] == 1
    assert body["incidents"]["by_sensor"] == {"0": 1}
    assert body["response_times"]["mean_seconds"] is None
    assert body["devices"][0]["status"] == "unknown"


def test_large_query_is_explicitly_rejected(analytics_db, monkeypatch):
    m, c = analytics_db
    for ts in [0, 1000, 2000]:
        insert(c, ts, False)
    monkeypatch.setattr(m, "MAX_READINGS", 2)
    assert m.load_data(c, 0, 3000, 10000) is None


def test_legacy_records_not_merged_with_incidents(analytics_db):
    m, c = analytics_db
    with c.cursor() as cur:
        cur.execute("INSERT INTO devices (id,name,zone_id) VALUES (1,'legacy',3)")
        cur.execute("INSERT INTO spill_events (device_id,status) VALUES (1,'wet')")
    data = m.load_data(c, 0, 3000, 10000)
    assert data["legacy_spill_records"][0]["zone_id"] == 3
    assert m.incident_summary(data["readings"], 0, 3000, {})["incident_count"] == 0
