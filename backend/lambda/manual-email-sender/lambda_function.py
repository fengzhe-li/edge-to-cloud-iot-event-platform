import os
from spill_common import observed, body_object
import json
import boto3

REGION = os.environ.get("AWS_REGION", "eu-north-1")
ses = boto3.client("ses", region_name=REGION)

SENDER = os.environ.get("SENDER", "operations@example.com")


@observed("manual_email", api=True)
def lambda_handler(event, context):
    headers = {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Headers": "Content-Type",
        "Access-Control-Allow-Methods": "POST, OPTIONS",
    }

    method = event.get("httpMethod") or event.get("requestContext", {}).get(
        "http", {}
    ).get("method")

    if method == "OPTIONS":
        return {"statusCode": 200, "headers": headers, "body": ""}

    if method != "POST":
        return {
            "statusCode": 405,
            "body": json.dumps({"ok": False, "error": "Method not allowed"}),
        }

    body = body_object(event)
    try:
        to_list = body.get("to", ["operations@example.com"])
        subject = body.get("subject", "WET Alert")
        message = body.get("message", "Shelves need to be cleaned!")

        if isinstance(to_list, str):
            to_list = [to_list]

        if not isinstance(to_list, list):
            raise ValueError("to must be a string or list")
        if not isinstance(subject, str) or not isinstance(message, str):
            raise ValueError("subject and message must be strings")

        # 清理邮箱字符串
        to_list = [
            email.strip()
            for email in to_list
            if isinstance(email, str) and email.strip()
        ]

        if not to_list or not subject or not message:
            return {
                "statusCode": 400,
                "headers": headers,
                "body": json.dumps(
                    {"error": "Missing required fields: to, subject, message"}
                ),
            }

        response = ses.send_email(
            Source=SENDER,
            Destination={"ToAddresses": to_list},
            Message={
                "Subject": {"Data": subject, "Charset": "UTF-8"},
                "Body": {"Text": {"Data": message, "Charset": "UTF-8"}},
            },
        )

        return {
            "statusCode": 200,
            "headers": headers,
            "body": json.dumps(
                {
                    "message": "Email sent successfully",
                    "messageId": response["MessageId"],
                }
            ),
        }

    except Exception:
        raise
