"""Shared validation and structured logs; no network access at import time."""

import functools
import json
import math
from datetime import datetime, timezone


def log(level, outcome, **fields):
    print(
        json.dumps(
            {
                "level": level,
                "outcome": outcome,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                **fields,
            },
            default=str,
        )
    )


def pick(event, *keys):
    return next((event[k] for k in keys if event.get(k) is not None), None)


def integer(value, field, minimum=0):
    if isinstance(value, bool) or value is None:
        raise ValueError(f"{field} must be an integer")
    try:
        number = float(value)
        result = int(value)
    except (ValueError, TypeError, OverflowError):
        raise ValueError(f"{field} must be an integer") from None
    if not math.isfinite(number) or number != result or result < minimum:
        raise ValueError(f"{field} must be an integer >= {minimum}")
    return result


def event_time(event):
    """Publisher time takes priority. Generic timestamp/ts accept epoch s or ms."""
    value = pick(event, "event_ts_ms", "timestamp", "ts")
    if value is not None:
        ts = integer(value, "event timestamp")
        if event.get("event_ts_ms") is None and ts < 10_000_000_000:
            ts *= 1000
    else:
        value = event.get("received_ts")
        ts = (
            integer(value, "received_ts")
            if value is not None
            else int(datetime.now(timezone.utc).timestamp() * 1000)
        )
    try:
        at = datetime.fromtimestamp(ts / 1000, timezone.utc)
    except (ValueError, OverflowError, OSError):
        raise ValueError("event timestamp out of range") from None
    return ts, at


def observed(event_type, api=False):
    def decorate(fn):
        @functools.wraps(fn)
        def wrapped(event, context):
            fields = {
                "request_id": getattr(context, "aws_request_id", None),
                "event_type": event_type,
                "event_id": event.get("event_id") if isinstance(event, dict) else None,
            }
            try:
                if not isinstance(event, dict):
                    raise ValueError("event must be an object")
                result = fn(event, context)
                failed = isinstance(result, dict) and (
                    result.get("statusCode", 200) >= 400 or result.get("ok") is False
                )
                details = {
                    k: result[k]
                    for k in (
                        "event_key",
                        "duplicate",
                        "skipped",
                        "current_state_updated",
                        "deduplication_available",
                    )
                    if isinstance(result, dict) and k in result
                }
                if isinstance(result, dict) and "type" in result:
                    fields["event_type"] = result["type"]
                log(
                    "ERROR" if failed else "INFO",
                    "rejected" if failed else "completed",
                    **fields,
                    **details,
                )
                return result
            except Exception as exc:
                log("ERROR", "failed", failure_category=type(exc).__name__, **fields)
                if api:
                    return response(
                        400 if isinstance(exc, ValueError) else 500,
                        {
                            "ok": False,
                            "error": str(exc)
                            if isinstance(exc, ValueError)
                            else "Internal service error",
                        },
                    )
                raise

        return wrapped

    return decorate


def response(code, body):
    return {
        "statusCode": code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body, default=str),
    }


def body_object(event):
    try:
        body = event.get("body") or "{}"
        result = json.loads(body) if isinstance(body, str) else body
    except (TypeError, json.JSONDecodeError):
        raise ValueError("Invalid JSON body") from None
    if not isinstance(result, dict):
        raise ValueError("body must be an object")
    return result
