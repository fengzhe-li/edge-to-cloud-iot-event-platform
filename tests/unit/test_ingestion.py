import json
from unittest.mock import MagicMock
import pytest
from spill_common import integer, event_time

BASE = {
    "deviceId": "Arduino1",
    "sensorId": 0,
    "state": " wet ",
    "raw": 0,
    "received_ts": 1700000000000,
}


@pytest.mark.parametrize("value", [None, True, "bad", -1, 1.5, float("inf")])
def test_invalid_integer(value):
    with pytest.raises(ValueError):
        integer(value, "field")


def test_zero_and_alias_normalization(loader):
    d = loader("database-ingest").normalize(BASE)
    assert (d["sensor_id"], d["value"], d["wet"], d["state"]) == (0, 0, True, "WET")


@pytest.mark.parametrize(
    "state,wet", [("WET", True), ("DRY", False), ("DRYING", False)]
)
def test_states(loader, state, wet):
    assert loader("database-ingest").normalize({**BASE, "state": state})["wet"] is wet


@pytest.mark.parametrize(
    "changes",
    [
        {"deviceId": ""},
        {"sensorId": None},
        {"state": "bad"},
        {"received_ts": "x"},
        {"raw": False},
    ],
)
def test_invalid_sensor(loader, changes):
    with pytest.raises(ValueError):
        loader("database-ingest").normalize({**BASE, **changes})


def test_rfid_aliases_and_seconds(loader):
    d = loader("database-ingest").normalize(
        {
            "deviceId": "A",
            "rfidId": "reader",
            "rfidUid": " abcd ",
            "timestamp": 1700000000,
        }
    )
    assert (d["type"], d["rfid_uid"], d["ts"]) == ("rfid", "ABCD", 1700000000000)


@pytest.mark.parametrize("field", ["rfidId", "rfidUid", "deviceId"])
def test_required_rfid(loader, field):
    event = {"deviceId": "A", "rfidId": "r", "rfidUid": "u", "mqtt_topic": "rfid"}
    del event[field]
    with pytest.raises(ValueError):
        loader("database-ingest").normalize(event)


def test_heartbeat_classification(loader):
    d = loader("database-ingest").normalize(
        {"type": "heartbeat", "source": "A", "uptimeMs": 0}
    )
    assert d["type"] == "heartbeat" and d["uptime_ms"] == 0 and d["device_id"] == "A"


def test_publisher_timestamp_precedes_receipt():
    assert (
        event_time({"timestamp": 1700000000, "received_ts": 1800000000000})[0]
        == 1700000000000
    )


def test_event_identity_stable_across_receipts(loader):
    normalize = loader("database-ingest").normalize
    a = normalize({**BASE, "event_id": "one"})
    b = normalize({**BASE, "event_id": "one", "received_ts": 1800000000000})
    assert a["event_key"] == b["event_key"] and a["fingerprint"] == b["fingerprint"]
    c = normalize({**BASE, "event_id": "one", "state": "DRY"})
    assert a["event_key"] == c["event_key"] and a["fingerprint"] != c["fingerprint"]


def test_no_stable_identity_is_not_deduplicated(loader):
    event = {k: v for k, v in BASE.items() if k != "received_ts"}
    assert loader("database-ingest").normalize(event)["event_key"] is None


def database(module, monkeypatch):
    conn = MagicMock()
    cur = conn.cursor.return_value.__enter__.return_value
    monkeypatch.setattr(module.psycopg2, "connect", lambda **kw: conn)
    cur.fetchone.return_value = ("key",)
    cur.rowcount = 1
    return conn, cur


def test_history_and_current_share_transaction(loader, monkeypatch, ctx):
    m = loader("database-ingest")
    conn, cur = database(m, monkeypatch)
    result = m.lambda_handler(BASE, ctx)
    calls = cur.execute.call_args_list
    assert len(calls) == 3
    assert "INSERT INTO waterlevel_readings" in calls[1].args[0]
    assert calls[1].args[1][4:7] == (0, 0, True)
    assert json.loads(calls[1].args[1][-1]) == BASE
    assert "EXCLUDED.updated_ts > sensorstate.updated_ts" in calls[2].args[0]
    assert result["ok"] and result["current_state_updated"]
    assert conn.__exit__.call_args.args == (None, None, None)
    conn.close.assert_called_once()


def test_duplicate_does_not_insert_history(loader, monkeypatch, ctx):
    m = loader("database-ingest")
    conn, cur = database(m, monkeypatch)
    cur.fetchone.side_effect = [None, (m.normalize(BASE)["fingerprint"],)]
    assert m.lambda_handler(BASE, ctx)["duplicate"]
    assert len(cur.execute.call_args_list) == 2


def test_failure_rolls_back_and_propagates(loader, monkeypatch, ctx):
    m = loader("database-ingest")
    conn, cur = database(m, monkeypatch)
    cur.execute.side_effect = [None, RuntimeError("database down")]
    with pytest.raises(RuntimeError):
        m.lambda_handler(BASE, ctx)
    assert conn.__exit__.call_args.args[0] is RuntimeError
    conn.close.assert_called_once()
