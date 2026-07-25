# IoT message flow

1. IoT devices publish sensor readings over MQTT.
2. AWS IoT Core authenticates each device using X.509 certificates.
3. IoT Rules route messages to Lambda functions.
4. Lambda functions persist data and evaluate spill conditions.
5. Alert functions send email notifications and expose status through API Gateway.
6. The frontend dashboard polls the API and visualises sensor state.

This document is intentionally generic and contains no production identifiers.
