# System architecture

## Data ingestion

Devices publish sensor readings and heartbeat messages through MQTT. AWS IoT
Core authenticates devices with X.509 certificates and routes messages with IoT
Rules.

## Processing

Lambda functions validate events, update current state, persist historical
records, and trigger notifications. PostgreSQL stores relational event history;
DynamoDB stores small low-latency operational state.

## Application access

API Gateway exposes status, configuration, actuator and notification endpoints.
The browser dashboard visualises zones, sensor state, RFID activity and audit
events.

## Delivery and identity

Static files are delivered through S3 and CloudFront. Cognito represents the
recommended production authentication path, while IAM separates AWS service
permissions by responsibility.
