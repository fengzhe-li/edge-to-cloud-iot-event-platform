import os
import json
import time
import boto3
from datetime import datetime, timezone
from botocore.exceptions import ClientError

REGION = os.environ.get("AWS_REGION", "eu-north-1")

ses = boto3.client("ses", region_name=REGION)
dynamodb = boto3.resource("dynamodb", region_name=REGION)

TABLE_NAME = os.environ.get("ALERT_TABLE", "sensor_alert_state")
table = dynamodb.Table(TABLE_NAME)

SENDER = os.environ.get("SENDER", "operations@example.com")
RECIPIENTS = [
    x.strip()
    for x in os.environ.get("RECIPIENTS", "operations@example.com").split(",")
    if x.strip()
]


def log(level: str, msg: str, **kwargs):
    payload = {
        "level": level.upper(),
        "msg": msg,
        "ts": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }
    if kwargs:
        payload.update(kwargs)
    print(json.dumps(payload, default=str))


def _pick_field(event: dict, *keys):
    for k in keys:
        if k in event:
            return event[k]
    return None


def _derive_state(event: dict):
    st = _pick_field(event, "state", "status")
    if st is None:
        return None
    state_str = str(st).strip().upper()
    if state_str not in {"WET", "DRY", "DRYING"}:
        return None
    return state_str


def lambda_handler(event, context):
    log(
        "INFO",
        "Lambda invoked",
        request_id=getattr(context, "aws_request_id", None),
        event=event,
    )

    try:
        sensor_id_raw = _pick_field(event, "sensor_id", "sensorId")
        sensor_id = str(sensor_id_raw).strip() if sensor_id_raw is not None else None

        zone_name = (
            _pick_field(event, "zone_name", "zoneName", "zone", "location", "area")
            or "Unknown Zone"
        )

        device_id = _pick_field(event, "device_id", "deviceId", "source_id") or "UNKNOWN_DEVICE"
        mqtt_topic = _pick_field(event, "mqtt_topic", "topic") or "unknown"

        received_ts = _pick_field(event, "received_ts", "ts")
        if received_ts is None:
            received_ts = int(time.time() * 1000)
        else:
            received_ts = int(received_ts)

        received_at = datetime.fromtimestamp(received_ts / 1000, tz=timezone.utc)
        current_state = _derive_state(event)

        log(
            "INFO",
            "Parsed event",
            sensor_id=sensor_id,
            zone_name=zone_name,
            device_id=device_id,
            mqtt_topic=mqtt_topic,
            current_state=current_state,
            received_ts=received_ts,
        )

        if not sensor_id:
            return {"ok": False, "error": "missing sensor_id"}

        if current_state is None:
            return {"ok": True, "skipped": True, "reason": "invalid or missing state"}

        if current_state == "DRYING":
            current_state = "DRY"

        resp = table.get_item(Key={"sensor_id": sensor_id})
        item = resp.get("Item")
        previous_state = item.get("last_state") if item else None

        log(
            "INFO",
            "Loaded previous state",
            sensor_id=sensor_id,
            previous_state=previous_state,
            current_state=current_state,
        )

        email_sent = False
        message = "no action"

        if previous_state in (None, "DRY") and current_state == "WET":
            subject = f"Moisture detected in {zone_name}"
            body_text = (
                f"Hello,\n\n"
                f"Moisture has been detected by the monitoring system.\n\n"
                f"Location: {zone_name}\n"
                f"Sensor ID: {sensor_id}\n"
                f"Device ID: {device_id}\n"
                f"Current state: {current_state}\n"
                f"Detected at: {received_at.strftime('%Y-%m-%d %H:%M:%S UTC')}\n"
                f"MQTT topic: {mqtt_topic}\n\n"
                f"Please check the area.\n\n"
                f"Monitoring System"
            )

            ses.send_email(
                Source=SENDER,
                Destination={"ToAddresses": RECIPIENTS},
                Message={
                    "Subject": {"Data": subject, "Charset": "UTF-8"},
                    "Body": {
                        "Text": {"Data": body_text, "Charset": "UTF-8"}
                    }
                }
            )

            email_sent = True
            message = "dry->wet detected, email sent"

        elif previous_state == "WET" and current_state == "WET":
            message = "still wet, no email sent"

        elif previous_state == "WET" and current_state == "DRY":
            message = "wet->dry detected, no email sent"

        elif previous_state == "DRY" and current_state == "DRY":
            message = "still dry, no email sent"

        elif previous_state is None:
            message = "first state recorded, no email sent"

        else:
            message = f"{previous_state}->{current_state}, no email sent"

        table.put_item(
            Item={
                "sensor_id": sensor_id,
                "last_state": current_state,
                "zone_name": zone_name,
                "device_id": device_id,
                "updated_ts": received_ts,
                "updated_at": received_at.isoformat(),
            }
        )

        log(
            "INFO",
            "State updated",
            sensor_id=sensor_id,
            previous_state=previous_state,
            current_state=current_state,
            email_sent=email_sent,
            message=message,
        )

        return {
            "ok": True,
            "sensor_id": sensor_id,
            "previous_state": previous_state,
            "current_state": current_state,
            "email_sent": email_sent,
            "message": message,
        }

    except ClientError as e:
        log("ERROR", "AWS error", error=str(e))
        return {"ok": False, "error": str(e)}

    except Exception as e:
        log("ERROR", "General error", error=str(e))
        return {"ok": False, "error": str(e)}