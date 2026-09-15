import json
from unittest.mock import MagicMock
import pytest


def request(method, path="/", body=None):
    return {
        "httpMethod": method,
        "path": path,
        "body": json.dumps(body) if body is not None else None,
    }


@pytest.mark.parametrize(
    "name",
    [
        "automatic-alert",
        "database-ingest",
        "eventbridge-email-notifier",
        "led-control",
        "manual-email-sender",
        "sensor-config",
        "sensor-data-processor",
        "status-api",
    ],
)
def test_handler_imports(loader, name):
    assert callable(loader(name).lambda_handler)


@pytest.mark.parametrize("body", [[], "bad", None, 1])
def test_config_rejects_invalid_body(loader, ctx, body):
    m = loader("sensor-config")
    result = m.lambda_handler(request("POST", "/config/A/update", body), ctx)
    assert result["statusCode"] == 400


def test_config_strict_boolean(loader, ctx):
    m = loader("sensor-config")
    result = m.lambda_handler(
        request("POST", "/config/A/update", {"sensor_id": 0, "active": "false"}), ctx
    )
    assert result["statusCode"] == 400


def test_config_update_values(loader, ctx, monkeypatch):
    m = loader("sensor-config")
    execute = MagicMock(return_value=1)
    monkeypatch.setattr(m, "_db_execute", execute)
    result = m.lambda_handler(
        request("POST", "/config/A/update", {"sensor_id": 0, "active": False}), ctx
    )
    assert result["statusCode"] == 200
    assert execute.call_args.args[1] == (False, "A", 0)


@pytest.mark.parametrize("value", [-1, True, "bad"])
def test_threshold_rejects_invalid_values(loader, ctx, value):
    result = loader("sensor-config").lambda_handler(
        request(
            "POST", "/threshold/A/update", {"sensor_id": 0, "threshold_value": value}
        ),
        ctx,
    )
    assert result["statusCode"] == 400


def test_threshold_push_payload(loader, ctx, monkeypatch):
    m = loader("sensor-config")
    monkeypatch.setattr(m, "_db_fetch", lambda *args: [(0, 123), (1, 456)])
    client = MagicMock()
    monkeypatch.setattr(m, "iot_data", client)
    result = m.lambda_handler(
        request("POST", "/threshold/push", {"device_id": "A"}), ctx
    )
    assert result["statusCode"] == 200
    kwargs = client.publish.call_args.kwargs
    assert kwargs["topic"] == "config/A/thresholds" and kwargs["qos"] == 1
    assert json.loads(kwargs["payload"]) == {"thresholds": {"0": 123, "1": 456}}


def test_api_error_redacted(loader, ctx, monkeypatch):
    m = loader("sensor-config")
    monkeypatch.setattr(
        m, "_db_fetch", MagicMock(side_effect=RuntimeError("password=secret"))
    )
    result = m.lambda_handler(request("GET", "/config/A"), ctx)
    assert result["statusCode"] == 500 and "secret" not in result["body"]


def test_manual_email_body_and_method(loader, ctx, monkeypatch):
    m = loader("manual-email-sender")
    ses = MagicMock()
    ses.send_email.return_value = {"MessageId": "id"}
    monkeypatch.setattr(m, "ses", ses)
    assert m.lambda_handler(request("GET"), ctx)["statusCode"] == 405
    result = m.lambda_handler(
        request(
            "POST", body={"to": " a@example.com ", "subject": "Alert", "message": "Wet"}
        ),
        ctx,
    )
    assert result["statusCode"] == 200
    assert ses.send_email.call_args.kwargs["Destination"] == {
        "ToAddresses": ["a@example.com"]
    }


def test_status_failure_and_method(loader, ctx, monkeypatch):
    m = loader("status-api")
    monkeypatch.setattr(
        m.pg8000, "connect", MagicMock(side_effect=RuntimeError("down"))
    )
    assert m.lambda_handler(request("POST"), ctx)["statusCode"] == 405
    assert m.lambda_handler(request("GET"), ctx)["statusCode"] == 500


def test_status_sensor_response(loader, ctx, monkeypatch):
    m = loader("status-api")
    conn = MagicMock()
    cur = conn.cursor.return_value
    cur.fetchall.return_value = []
    cur.fetchone.return_value = (0, True, 1700000000000, "WET", None, 42, "topic", {})
    monkeypatch.setattr(m.pg8000, "connect", lambda **kw: conn)
    result = m.lambda_handler(
        {"httpMethod": "GET", "queryStringParameters": {"sensor_id": "0"}}, ctx
    )
    assert json.loads(result["body"])["sensor"]["status"] == "wet"
    assert cur.execute.call_args.args[1] == ("0",)
    conn.close.assert_called_once()


@pytest.mark.parametrize(
    "body",
    [
        {"systemId": "system3", "state": "on"},
        {"systemId": "system1", "state": "bad"},
        [],
    ],
)
def test_led_validation(loader, ctx, body):
    assert (
        loader("led-control").lambda_handler(request("POST", body=body), ctx)[
            "statusCode"
        ]
        == 400
    )


def test_legacy_database_failure_never_alerts(loader, ctx, monkeypatch):
    m = loader("sensor-data-processor")
    monkeypatch.setattr(
        m.psycopg2, "connect", MagicMock(side_effect=RuntimeError("undefined function"))
    )
    client = MagicMock()
    monkeypatch.setattr(m.boto3, "client", client)
    with pytest.raises(RuntimeError):
        m.lambda_handler({}, ctx)
    client.assert_not_called()
