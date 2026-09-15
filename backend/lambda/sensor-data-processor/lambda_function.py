"""Legacy export: stored-function contract is absent; not in supported deployment."""

import json
import os
import boto3
import psycopg2
from spill_common import observed


@observed("legacy_sensor_processor")
def lambda_handler(event, context):
    conn = psycopg2.connect(
        host=os.environ["DB_HOST"],
        dbname=os.environ["DB_NAME"],
        user=os.environ["DB_USER"],
        password=os.environ["DB_PASS"],
    )
    try:
        with conn:
            with conn.cursor() as cur:
                # Intentionally not fabricated. UndefinedFunction propagates.
                cur.execute("SELECT insert_sensor_json(%s)", (json.dumps(event),))
    finally:
        conn.close()
    result = boto3.client("lambda").invoke(
        FunctionName=os.environ["ALERT_FUNCTION_NAME"],
        InvocationType="Event",
        Payload=json.dumps(event),
    )
    if result.get("StatusCode") != 202:
        raise RuntimeError("Alert invocation not accepted")
    return {"ok": True, "alert_accepted": True}
