"""Atomic state acceptance before SES; at most one attempt per accepted transition.

A crash after claim can lose an alert. No automatic resend after an ambiguous SES
failure: this intentionally avoids claiming exactly-once or guaranteed delivery.
"""

import os
import boto3
from botocore.exceptions import ClientError
from spill_common import event_time, observed, pick, log


@observed("automatic_alert")
def lambda_handler(event, context):
    sid = pick(event, "sensor_id", "sensorId")
    if sid is None or not str(sid).strip():
        raise ValueError("missing sensor_id")
    state = str(pick(event, "state", "status") or "").strip().upper()
    if state not in ("WET", "DRY", "DRYING"):
        raise ValueError("invalid state")
    state = "DRY" if state == "DRYING" else state
    ts, at = event_time(event)
    recipients = [s.strip() for s in os.environ["RECIPIENTS"].split(",") if s.strip()]
    sender = os.environ["SENDER"].strip()
    if not recipients or not sender:
        raise ValueError("SENDER and RECIPIENTS are required")
    table = boto3.resource("dynamodb").Table(
        os.getenv("ALERT_TABLE", "sensor_alert_state")
    )
    # Compare-and-swap retries only state contention, never SES delivery.
    for _ in range(8):
        old = table.get_item(Key={"sensor_id": str(sid)}, ConsistentRead=True).get(
            "Item"
        )
        if old and ts <= int(old.get("updated_ts", -1)):
            return {"ok": True, "skipped": "stale_or_duplicate", "email_sent": False}
        values = {":state": state, ":ts": ts, ":at": at.isoformat()}
        condition = "attribute_not_exists(sensor_id)"
        if old:
            condition = "last_state = :previous AND updated_ts = :previous_ts"
            if "updated_ts" not in old:
                raise ValueError("legacy alert state requires updated_ts migration")
            values.update(
                {":previous": old["last_state"], ":previous_ts": old["updated_ts"]}
            )
        try:
            table.update_item(
                Key={"sensor_id": str(sid)},
                UpdateExpression="SET last_state=:state, updated_ts=:ts, updated_at=:at",
                ConditionExpression=condition,
                ExpressionAttributeValues=values,
            )
            break
        except ClientError as exc:
            if exc.response["Error"]["Code"] != "ConditionalCheckFailedException":
                raise
    else:
        raise RuntimeError("alert state contention exhausted")
    should_send = state == "WET" and (not old or old["last_state"] != "WET")
    if should_send:
        boto3.client("ses").send_email(
            Source=sender,
            Destination={"ToAddresses": recipients},
            Message={
                "Subject": {"Data": f"Moisture detected: sensor {sid}"},
                "Body": {
                    "Text": {"Data": f"Sensor {sid} entered WET at {at.isoformat()}."}
                },
            },
        )
    log(
        "INFO",
        "alert_transition_accepted",
        sensor_id=str(sid),
        event_ts=ts,
        email_sent=should_send,
        request_id=getattr(context, "aws_request_id", None),
    )
    return {"ok": True, "email_sent": should_send, "state": state}
