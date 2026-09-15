"""Handler + real boto3 calls against Moto's DynamoDB emulator, not live AWS."""

from concurrent.futures import ThreadPoolExecutor
from unittest.mock import MagicMock
import boto3
from moto import mock_aws
import pytest


@pytest.fixture
def alert(loader, monkeypatch):
    with mock_aws():
        boto3.resource("dynamodb").create_table(
            TableName="sensor_alert_state",
            KeySchema=[{"AttributeName": "sensor_id", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "sensor_id", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )
        m = loader("automatic-alert")
        ses = MagicMock()
        original = boto3.client
        monkeypatch.setattr(
            m.boto3,
            "client",
            lambda service, *a, **kw: ses
            if service == "ses"
            else original(service, *a, **kw),
        )
        yield m, ses


def event(ts, state="WET"):
    return {"sensor_id": 0, "event_ts_ms": ts, "state": state}


def test_transitions_and_stale_events(alert, ctx):
    m, ses = alert
    assert m.lambda_handler(event(1000), ctx)["email_sent"]
    assert not m.lambda_handler(event(2000), ctx)["email_sent"]
    assert m.lambda_handler(event(500, "DRY"), ctx)["skipped"] == "stale_or_duplicate"
    assert not m.lambda_handler(event(3000, "DRY"), ctx)["email_sent"]
    assert m.lambda_handler(event(4000), ctx)["email_sent"]
    assert ses.send_email.call_count == 2


def test_parallel_duplicate_transition(alert, ctx):
    m, ses = alert
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(
            pool.map(lambda _: m.lambda_handler(event(1000), ctx), range(12))
        )
    assert sum(r["email_sent"] for r in results) == 1
    assert ses.send_email.call_count == 1


def test_send_failure_is_not_silently_successful_or_retried(alert, ctx):
    m, ses = alert
    ses.send_email.side_effect = RuntimeError("uncertain delivery")
    with pytest.raises(RuntimeError):
        m.lambda_handler(event(1000), ctx)
    assert not m.lambda_handler(event(1000), ctx)["email_sent"]
    assert ses.send_email.call_count == 1


def test_drying_resets_transition(alert, ctx):
    m, ses = alert
    m.lambda_handler(event(1000), ctx)
    m.lambda_handler(event(2000, "DRYING"), ctx)
    assert m.lambda_handler(event(3000), ctx)["email_sent"]
