import json
import boto3
from botocore.exceptions import ClientError

REGION = os.environ.get("AWS_REGION", "eu-north-1")
ses = boto3.client("ses", region_name=REGION)

SENDER = "operations@example.com"

def lambda_handler(event, context):
    headers = {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Headers": "Content-Type",
        "Access-Control-Allow-Methods": "POST, OPTIONS"
    }

    method = event.get("httpMethod") or event.get("requestContext", {}).get("http", {}).get("method")

    if method == "OPTIONS":
        return {
            "statusCode": 200,
            "headers": headers,
            "body": ""
        }

    try:
        body = json.loads(event.get("body", "{}"))

        to_list = body.get("to", ["operations@example.com"])
        subject = body.get("subject", "WET Alert")
        message = body.get("message", "Shelves need to be cleaned!")

        if isinstance(to_list, str):
            to_list = [to_list]

        # 清理邮箱字符串
        to_list = [email.strip() for email in to_list if isinstance(email, str) and email.strip()]

        if not to_list or not subject or not message:
            return {
                "statusCode": 400,
                "headers": headers,
                "body": json.dumps({
                    "error": "Missing required fields: to, subject, message"
                })
            }

        response = ses.send_email(
            Source=SENDER,
            Destination={
                "ToAddresses": to_list
            },
            Message={
                "Subject": {
                    "Data": subject,
                    "Charset": "UTF-8"
                },
                "Body": {
                    "Text": {
                        "Data": message,
                        "Charset": "UTF-8"
                    }
                }
            }
        )

        return {
            "statusCode": 200,
            "headers": headers,
            "body": json.dumps({
                "message": "Email sent successfully",
                "messageId": response["MessageId"]
            })
        }

    except ClientError as e:
        print("SES Error:", e.response["Error"]["Message"])
        return {
            "statusCode": 500,
            "headers": headers,
            "body": json.dumps({"error": e.response["Error"]["Message"]})
        }

    except Exception as e:
        print("Error:", str(e))
        return {
            "statusCode": 500,
            "headers": headers,
            "body": json.dumps({"error": str(e)})
        }