# Amazon DynamoDB infrastructure

This directory contains a sanitised portfolio export of the DynamoDB resources
used by the AWS IoT smart spill detection system.

## Included

- Table metadata and key schema
- Billing and capacity configuration where available
- Index definitions where available
- Stream and TTL settings where available

## Tables

- `ActuatorState`
- `sensor_alert_state`

## Excluded

Real DynamoDB item data, credentials, access keys, session tokens, and live AWS
account identifiers are not included in this repository.

## Security notes

- Do not commit production item exports.
- Use least-privilege IAM permissions for table access.
- Enable point-in-time recovery for production tables.
- Use encryption at rest and CloudTrail auditing.
- Store configuration outside source control where appropriate.

## Files processed

Included configuration files: 4
Skipped unsupported files: 0
