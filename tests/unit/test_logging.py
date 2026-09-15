import json
import pytest
from spill_common import observed


def test_error_log_has_context_without_secret(capsys, ctx):
    @observed("test", api=True)
    def handler(event, context):
        raise RuntimeError("password=do-not-log")

    result = handler({"event_id": "one"}, ctx)
    output = capsys.readouterr().out
    record = json.loads(output)
    assert record["request_id"] == "request-test" and record["event_id"] == "one"
    assert record["failure_category"] == "RuntimeError"
    assert "do-not-log" not in output + result["body"]
    assert result["statusCode"] == 500


def test_event_failure_propagates(ctx):
    @observed("test")
    def handler(event, context):
        raise RuntimeError("failure")

    with pytest.raises(RuntimeError):
        handler({}, ctx)


def test_invalid_event_returns_bad_request(ctx):
    @observed("test", api=True)
    def handler(event, context):
        raise AssertionError("unreachable")

    assert handler([], ctx)["statusCode"] == 400


def test_duplicate_outcome_is_logged(capsys, ctx):
    @observed("ingestion")
    def handler(event, context):
        return {"ok": True, "type": "sensor", "event_key": "key", "duplicate": True}

    handler({}, ctx)
    record = json.loads(capsys.readouterr().out)
    assert (
        record["duplicate"]
        and record["event_type"] == "sensor"
        and record["event_key"] == "key"
    )
