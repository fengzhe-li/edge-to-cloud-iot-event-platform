from spill_common import observed, body_object
import json
import os
from datetime import datetime, timezone

import boto3

REGION = os.environ.get("AWS_REGION", "eu-north-1")
TABLE_NAME = os.environ.get("TABLE_NAME", "ActuatorState")
IOT_ENDPOINT = os.environ.get("IOT_ENDPOINT", "")
ENABLE_IOT_PUBLISH = os.environ.get("ENABLE_IOT_PUBLISH", "false").lower() == "true"

dynamodb = boto3.resource("dynamodb", region_name=REGION)
table = dynamodb.Table(TABLE_NAME)

iot_client = None
if ENABLE_IOT_PUBLISH and IOT_ENDPOINT:
    iot_client = boto3.client(
        "iot-data", region_name=REGION, endpoint_url=f"https://{IOT_ENDPOINT}"
    )


def json_response(status_code, body):
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Content-Type",
            "Access-Control-Allow-Methods": "OPTIONS,GET,POST",
        },
        "body": json.dumps(body),
    }


def parse_body(event):
    return body_object(event)


def get_method(event):
    return (
        event.get("requestContext", {}).get("http", {}).get("method")
        or event.get("httpMethod")
        or "GET"
    )


def is_valid_system_id(system_id):
    return system_id in ["system1", "system2"]


def is_valid_state(state):
    return state in ["on", "off"]


def get_now_iso():
    return datetime.now(timezone.utc).isoformat()


def get_all_states():
    response = table.get_item(Key={"pk": "actuator_state"})
    item = response.get("Item")

    if not item:
        return {
            "pk": "actuator_state",
            "system1": "off",
            "system2": "off",
            "updatedAt": None,
        }

    return item


def save_state(system_id, state):
    now = get_now_iso()

    table.update_item(
        Key={"pk": "actuator_state"},
        UpdateExpression="SET #sid = :state, updatedAt = :updatedAt",
        ExpressionAttributeNames={"#sid": system_id},
        ExpressionAttributeValues={":state": state, ":updatedAt": now},
    )

    return {"systemId": system_id, "state": state, "updatedAt": now}


def publish_to_iot(system_id, state):
    if not iot_client:
        return {"published": False, "reason": "IoT publish disabled"}

    topic = f"actuator/{system_id}/set"
    payload = {"systemId": system_id, "state": state, "timestamp": get_now_iso()}

    iot_client.publish(topic=topic, qos=1, payload=json.dumps(payload))

    return {"published": True, "topic": topic}


@observed("led_control", api=True)
def lambda_handler(event, context):
    try:
        method = get_method(event)

        if method == "OPTIONS":
            return json_response(200, {"ok": True})

        if method == "GET":
            states = get_all_states()
            return json_response(
                200,
                {
                    "success": True,
                    "data": {
                        "system1": states.get("system1", "off"),
                        "system2": states.get("system2", "off"),
                        "updatedAt": states.get("updatedAt"),
                    },
                },
            )

        if method == "POST":
            body = parse_body(event)
            system_id = body.get("systemId")
            state = body.get("state")

            if not is_valid_system_id(system_id):
                return json_response(
                    400,
                    {
                        "success": False,
                        "message": "systemId must be 'system1' or 'system2'",
                    },
                )

            if not is_valid_state(state):
                return json_response(
                    400, {"success": False, "message": "state must be 'on' or 'off'"}
                )

            save_result = save_state(system_id, state)
            iot_result = publish_to_iot(system_id, state)

            return json_response(
                200,
                {
                    "success": True,
                    "message": "Actuator state updated",
                    "data": {
                        "systemId": system_id,
                        "state": state,
                        "updatedAt": save_result["updatedAt"],
                        "iot": iot_result,
                    },
                },
            )

        return json_response(
            405, {"success": False, "message": f"Method {method} not allowed"}
        )

    except Exception:
        raise
