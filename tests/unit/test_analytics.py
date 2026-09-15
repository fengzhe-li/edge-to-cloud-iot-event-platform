import json
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

NOW = datetime(2026, 9, 6, 12, tzinfo=timezone.utc)


def row(id, ts, wet, device="A", sensor=0, state=None):
    return {
        "id": id,
        "received_ts": ts,
        "wet": wet,
        "device_id": device,
        "sensor_id": sensor,
        "raw": {"state": state} if state else {},
    }


@pytest.mark.parametrize(
    "params",
    [
        {"window_hours": 0},
        {"window_hours": "nan"},
        {"window_hours": 745},
        {"start": "2026-09-06T10:00:00", "end": "2026-09-06T11:00:00Z"},
        {"start": "2026-09-06T10:00:00Z"},
        {"window_hours": 1, "bogus": 2},
        {"start": "2026-09-06T10:00:00Z", "end": "2026-09-07T11:00:00Z"},
        {"start": "2026-09-06T11:00:00Z", "end": "2026-09-06T10:00:00Z"},
    ],
)
def test_bad_window(loader, params):
    with pytest.raises(ValueError):
        loader("analytics").parse_window(params, NOW)


def test_timezone_window(loader):
    start, end = loader("analytics").parse_window(
        {"start": "2026-09-06T11:00:00+01:00", "end": "2026-09-06T12:00:00+01:00"}, NOW
    )
    assert start.hour == 10 and end.hour == 11


def test_default_window(loader):
    start, end = loader("analytics").parse_window({}, NOW)
    assert (end - start).total_seconds() == 86400


@pytest.mark.parametrize(
    "last,reading,status,quiet",
    [
        (95000, 1000, "online", True),
        (95000, 98000, "online", False),
        (40000, None, "online", True),
        (39999, 98000, "offline", False),
        (100001, None, "unknown", False),
    ],
)
def test_health(loader, last, reading, status, quiet):
    rows = loader("analytics").device_health(
        [
            {
                "device_id": "A",
                "last_seen_ts": last,
                "last_seen_at": "time",
                "uptime_ms": 9000,
            }
        ],
        [{"device_id": "A", "last_sensor_ts": reading}],
        [],
        100000,
    )
    assert rows[0]["status"] == status and rows[0]["quiet_but_online"] == quiet
    assert (
        rows[0]["reported_uptime_seconds"] == 9
        and rows[0]["availability_percent"] is None
    )


def test_missing_heartbeat_unknown(loader):
    data = loader("analytics").device_health([], [], ["A"], 100000)
    assert data[0]["status"] == "unknown" and data[0]["reported_uptime_seconds"] is None


def test_incidents_not_wet_reading_count(loader):
    result = loader("analytics").incident_summary(
        [
            row(1, 10, False),
            row(2, 20, True),
            row(3, 30, True),
            row(4, 40, False),
            row(5, 50, True),
        ],
        15,
        60,
        {"0": 1},
    )
    assert result["incident_count"] == 2 and result["first_observed_wet_count"] == 0
    assert result["by_zone"] == {"1": 2} and result["by_device"] == {"A": 2}
    assert len(result["state_transitions"]) == 3


def test_first_wet_not_claimed_as_known_onset(loader):
    result = loader("analytics").incident_summary(
        [row(1, 20, True), row(2, 30, True)], 10, 40, {}
    )
    assert result["incident_count"] == 0 and result["first_observed_wet_count"] == 1
    assert result["recent_incidents"][0]["zone_id"] is None


def test_window_boundaries_and_frequency(loader):
    result = loader("analytics").incident_summary(
        [
            row(1, 0, False),
            row(2, 1000, True),
            row(3, 2000, False),
            row(4, 3601000, True),
        ],
        1000,
        3601000,
        {},
    )
    assert result["incident_count"] == 1 and result["events_per_hour"] == 1
    assert result["by_zone"] == {"unmapped": 1}


def test_multi_device_sensor_grouping(loader):
    result = loader("analytics").incident_summary(
        [row(1, 0, False), row(2, 10, True, device="B"), row(3, 20, True)], 1, 30, {}
    )
    assert result["incident_count"] == 1 and result["first_observed_wet_count"] == 1
    assert result["by_device"] == {"A": 1}


def test_ambiguous_timestamp_does_not_invent_incident(loader):
    result = loader("analytics").incident_summary(
        [row(1, 0, False), row(2, 10, True), row(3, 10, False), row(4, 20, True)],
        1,
        30,
        {},
    )
    assert result["incident_count"] == 0 and result["ambiguous_reading_count"] == 2


def test_drying_preserved(loader):
    result = loader("analytics").incident_summary(
        [row(1, 0, False, state="DRYING"), row(2, 10, True)], 1, 20, {}
    )
    assert result["incident_count"] == 1
    assert result["state_transitions"][0]["from_state"] == "DRYING"


def test_api_payload_and_unsupported_metrics(loader, ctx, monkeypatch):
    m = loader("analytics")
    conn = MagicMock()
    monkeypatch.setattr(m.psycopg2, "connect", lambda **kw: conn)
    monkeypatch.setattr(
        m,
        "load_data",
        lambda *args: {
            "readings": [],
            "heartbeats": [],
            "latest_readings": [],
            "configuration": [],
            "thresholds": [],
            "current_sensor_state": [],
            "rfid": {"scan_count": 7},
            "legacy_spill_records": [],
        },
    )
    result = m.lambda_handler(
        {"httpMethod": "GET", "queryStringParameters": {"window_hours": "1"}}, ctx
    )
    body = json.loads(result["body"])
    assert result["statusCode"] == 200 and body["incidents"]["incident_count"] == 0
    assert (
        body["response_times"]["mean_seconds"] is None
        and body["response_times"]["rfid_scans_in_window"] == 7
    )
    assert (
        not body["availability"]["supported"]
        and not body["configuration_history"]["supported"]
    )
    conn.set_session.assert_called_once_with(
        readonly=True, isolation_level="REPEATABLE READ"
    )
    conn.close.assert_called_once()


@pytest.mark.parametrize(
    "event,code",
    [
        ({"httpMethod": "POST"}, 405),
        ({"path": "/wrong"}, 404),
        ({"queryStringParameters": {"window_hours": 0}}, 400),
    ],
)
def test_api_validation(loader, ctx, event, code):
    assert loader("analytics").lambda_handler(event, ctx)["statusCode"] == code


def test_query_limit_not_silently_truncated(loader, ctx, monkeypatch):
    m = loader("analytics")
    conn = MagicMock()
    monkeypatch.setattr(m.psycopg2, "connect", lambda **kw: conn)
    monkeypatch.setattr(m, "load_data", lambda *args: None)
    assert m.lambda_handler({}, ctx)["statusCode"] == 422
    conn.close.assert_called_once()
