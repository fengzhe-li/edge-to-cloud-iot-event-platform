from spill_common import observed
import os
import boto3

# SES v2 client (Amazon Simple Email Service v2)
ses = boto3.client("sesv2")

# Env vars
SES_FROM_EMAIL = os.environ["SES_FROM_EMAIL"]  # must be verified in SES
SES_TO_EMAILS = os.environ["SES_TO_EMAILS"]  # comma-separated


@observed("eventbridge_email")
def lambda_handler(event, context):
    """
    Trigger: EventBridge rule (Amazon EventBridge)
    Expect: event["detail"] contains spill status info from the ingest Lambda.

    This function sends an email alert via SES (Amazon Simple Email Service).
    """

    detail = event.get("detail") or {}

    # Safety filter (in case EventBridge sends non-alert events)
    wet = detail.get("wet", None)
    if wet is not True:
        return {"ok": True, "skipped": True, "reason": "wet is not True", "wet": wet}

    store_id = detail.get("store_id", "UNKNOWN_STORE")
    zone_id = detail.get("zone_id", "UNKNOWN_ZONE")
    sensor_id = detail.get("sensor_id", "UNKNOWN_SENSOR")
    device_id = detail.get("device_id", "UNKNOWN_DEVICE")
    mqtt_topic = detail.get("mqtt_topic", "UNKNOWN_TOPIC")
    received_ts = detail.get("received_ts", "UNKNOWN_TS")
    event_id = detail.get("event_id", "UNKNOWN_EVENT")
    ts_iso = detail.get("ts_iso", "UNKNOWN_TIME")

    subject = f"[Spill Alert] WET detected | store={store_id} zone={zone_id} sensor={sensor_id}"

    body = (
        "Wet detected (spill alert).\n\n"
        f"Event ID: {event_id}\n"
        f"Time (UTC): {ts_iso}\n"
        f"Store: {store_id}\n"
        f"Zone: {zone_id}\n"
        f"Sensor: {sensor_id}\n"
        f"Device: {device_id}\n"
        f"MQTT Topic: {mqtt_topic}\n"
        f"Received TS (ms): {received_ts}\n"
        f"Wet: {wet}\n"
    )

    recipients = [x.strip() for x in SES_TO_EMAILS.split(",") if x.strip()]
    if not recipients:
        raise ValueError("SES_TO_EMAILS is empty")

    resp = ses.send_email(
        FromEmailAddress=SES_FROM_EMAIL,
        Destination={"ToAddresses": recipients},
        Content={
            "Simple": {
                "Subject": {"Data": subject, "Charset": "UTF-8"},
                "Body": {"Text": {"Data": body, "Charset": "UTF-8"}},
            }
        },
    )

    return {
        "ok": True,
        "sent_to": recipients,
        "message_id": resp.get("MessageId"),
        "event_id": event_id,
    }
