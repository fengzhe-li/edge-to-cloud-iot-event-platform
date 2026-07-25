# Led Control

Exposes actuator state through API Gateway, stores state in DynamoDB, and optionally publishes commands through AWS IoT Core.

## Security and configuration

This portfolio copy contains no production credentials or live resource
identifiers. Configure deployment values through Lambda environment variables
and AWS Secrets Manager. Do not commit database passwords, API keys, account
IDs, certificates, verified personal email addresses, or live endpoints.

See `lambda_function.py` for the environment variables used by this function.
