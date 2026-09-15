# AWS Lambda backend

Sanitised portfolio copy of the serverless backend for the AWS IoT smart spill
detection system.

## Functions

- `sensor-data-processor`: IoT event processing and alert dispatch
- `database-ingest`: PostgreSQL persistence for sensor, RFID and heartbeat data
- `status-api`: dashboard read API
- `sensor-config`: configuration and threshold management through IoT Core
- `led-control`: actuator control backed by DynamoDB
- `automatic-alert`: automatic SES alerting and deduplication
- `manual-email-sender`: manual alert API
- `eventbridge-email-notifier`: EventBridge-to-SES notification flow

## Repository decisions

A byte-for-byte duplicate export of `SensorDataProcessor` was omitted. The older
`SpillAlertMailer` prototype was also omitted because it contained placeholder
database credentials and recursively invoked a function with the same name.
The maintained alert implementations are documented above.

Generated third-party dependency folders from the original Lambda export were
not committed. Dependencies are instead declared in each function's
`requirements.txt`.

## Deployment security

The included SAM templates are illustrative and contain placeholders. Store
database credentials in AWS Secrets Manager or SSM Parameter Store, apply
least-privilege IAM policies, restrict CORS for production, and use verified SES
identities supplied through environment variables.

## Supported deployment boundary

Use the repository-root SAM template and docs/DEPLOYMENT.md. The legacy
sensor-data-processor stored-function contract is missing, and the EventBridge
consumer is unwired; neither is included in the supported deployment. Alert
suppression uses conditional state acceptance, with the delivery limitations in
docs/ENGINEERING.md.
