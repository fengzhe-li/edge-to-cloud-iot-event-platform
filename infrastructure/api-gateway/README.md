# API Gateway

Public-safe OpenAPI exports for the AWS IoT smart spill detection system.

## APIs

### Sensor Configuration API
- `GET /config/{device_id}`
- `GET /threshold/{device_id}`
- `POST /config/{device_id}/update`
- `POST /threshold/{device_id}/update`
- `POST /config/push`
- `POST /threshold/push`

### LED Control API
- `POST /led-control`

### Email Notification API
- `POST /send-email`

### Sensor Status API
- `GET /sensor-status`

## Sanitisation

Live API IDs, AWS account IDs, endpoints, and Lambda integration ARNs were replaced with placeholders.

## Production hardening

- Restrict wildcard CORS.
- Add Cognito/JWT authorization.
- Keep configuration outside source control.
- Use least-privilege IAM.
- Require TLS 1.2 or newer.
