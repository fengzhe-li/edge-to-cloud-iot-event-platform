"""Real PostgreSQL semantics; only an explicitly supplied disposable database."""

import os
from pathlib import Path
import psycopg2
import pytest

pytestmark = pytest.mark.postgres


@pytest.fixture
def db(loader, monkeypatch):
    url = os.getenv("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL not set: requires disposable PostgreSQL")
    connect = psycopg2.connect
    conn = connect(url)
    # Isolated schema; never touches public application tables.
    import uuid

    schema = "test_" + uuid.uuid4().hex
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute(f"CREATE SCHEMA {schema}")
        sql = (
            Path("backend/database/schema.sql")
            .read_text()
            .replace("public.", schema + ".")
        )
        cur.execute(sql)
        cur.execute(f"SET search_path TO {schema}")
    m = loader("database-ingest")

    def test_connect(**kw):
        c = connect(url)
        with c.cursor() as cur:
            cur.execute(f"SET search_path TO {schema}")
        c.commit()
        return c

    monkeypatch.setattr(m.psycopg2, "connect", test_connect)
    yield m, conn
    with conn.cursor() as cur:
        cur.execute(f"DROP SCHEMA {schema} CASCADE")
    conn.close()


def sensor(ts, state="WET", **kw):
    return {
        "device_id": "A",
        "sensor_id": 0,
        "state": state,
        "event_ts_ms": ts,
        "value": 1,
        **kw,
    }


def query(conn, sql):
    with conn.cursor() as cur:
        cur.execute(sql)
        return cur.fetchall()


def test_sensor_ordering_and_history(db, ctx):
    m, c = db
    m.lambda_handler(sensor(2000), ctx)
    m.lambda_handler(sensor(1000, "DRY"), ctx)
    assert query(c, "SELECT updated_ts,state FROM sensorstate") == [(2000, "WET")]
    assert query(c, "SELECT count(*) FROM waterlevel_readings") == [(2,)]


def test_duplicate_history(db, ctx):
    m, c = db
    m.lambda_handler(sensor(1000), ctx)
    assert m.lambda_handler(sensor(1000), ctx)["duplicate"]
    assert query(c, "SELECT count(*) FROM waterlevel_readings") == [(1,)]


def test_heartbeat_ordering(db, ctx):
    m, c = db
    for ts in [2000, 1000]:
        m.lambda_handler(
            {"device_id": "A", "type": "heartbeat", "event_ts_ms": ts}, ctx
        )
    assert query(c, "SELECT last_seen_ts FROM device_heartbeats") == [(2000,)]


def test_reused_id_conflict(db, ctx):
    m, c = db
    m.lambda_handler(sensor(1000, event_id="one"), ctx)
    with pytest.raises(ValueError):
        m.lambda_handler(sensor(1000, "DRY", event_id="one"), ctx)
    assert query(c, "SELECT count(*) FROM waterlevel_readings") == [(1,)]


def test_transaction_rollback_releases_ledger(db, ctx):
    m, c = db
    with c.cursor() as cur:
        cur.execute(
            "ALTER TABLE waterlevel_readings ADD CONSTRAINT test_value CHECK(value>10)"
        )
    with pytest.raises(psycopg2.IntegrityError):
        m.lambda_handler(sensor(1000), ctx)
    assert query(c, "SELECT count(*) FROM ingested_events") == [(0,)]
    with c.cursor() as cur:
        cur.execute("ALTER TABLE waterlevel_readings DROP CONSTRAINT test_value")
    assert m.lambda_handler(sensor(1000), ctx)["ok"]


def test_rfid_history_dedup(db, ctx):
    m, c = db
    e = {
        "deviceId": "A",
        "rfidId": "r",
        "rfidUid": " aa ",
        "timestamp": 1700000000,
        "event_id": "scan1",
    }
    m.lambda_handler(e, ctx)
    m.lambda_handler(e, ctx)
    assert query(c, "SELECT rfid_uid,scan_timestamp FROM rfid_scans") == [
        ("AA", 1700000000)
    ]


def test_concurrent_duplicate_ingestion(db, ctx):
    from concurrent.futures import ThreadPoolExecutor

    m, c = db
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(
            pool.map(
                lambda _: m.lambda_handler(sensor(1000, event_id="concurrent"), ctx),
                range(8),
            )
        )
    assert sum(not r["duplicate"] for r in results) == 1
    assert query(c, "SELECT count(*) FROM waterlevel_readings") == [(1,)]


def test_equal_time_does_not_replace_state(db, ctx):
    m, c = db
    m.lambda_handler(sensor(1000, event_id="first"), ctx)
    m.lambda_handler(sensor(1000, "DRY", event_id="second"), ctx)
    assert query(c, "SELECT state FROM sensorstate") == [("WET",)]
    assert query(c, "SELECT count(*) FROM waterlevel_readings") == [(2,)]
