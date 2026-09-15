# Backend deployment boundary

Use the repository-root `template.yaml` for the supported seven-function backend.
Per-function templates and infrastructure exports are historical/illustrative, not
an independently complete deployment. Their code/layer paths are corrected, but
placeholder accounts/layers/identities and old function references remain archival
configuration evidence. Do not combine their triggers with the root stack.

## Prerequisites and explicit inputs

- AWS SAM CLI and Docker for Linux-compatible dependency builds; Python 3.12 runtime.
- An existing PostgreSQL database reachable from supplied private subnet/security-group IDs.
- Verified SES sender and permitted recipients in the deployment region (SES sandbox
  restrictions still apply).
- Existing IoT devices, policies, certificates and the account's IoT data endpoint.
- VPC egress/endpoints for the configuration Lambda to reach IoT. Database SSL/network
  posture must be configured and reviewed for the target environment.

The template creates Lambdas, a common logging/validation layer, IoT rules, two
DynamoDB tables and an IAM-authorized REST API. It does not provision RDS, device
firmware, static hosting or browser authentication. It is not a production-readiness claim.

## Database preparation

For a new disposable database, apply `backend/database/schema.sql` and optionally
`sample-data.sql`. For an existing database, review and explicitly apply only
`backend/database/migrations/001_event_ledger.sql` before enabling ingestion.
No migration runs automatically. Back up and review any real database independently.

## Build and deployment

```sh
sam validate --lint --template-file template.yaml
sam build --use-container --template-file template.yaml
sam deploy --guided
```

Supply DBHost, DBName, DBUser, DBPassword, DBSubnets, DBSecurityGroups, Sender,
Recipients and IoTEndpoint. DBPassword is NoEcho but is still a Lambda environment
value; automatic Secrets Manager retrieval is not implemented. Do not save real
parameters in tracked files or shell history. SAM generated output/config stays local.

Root endpoints: GET /sensor-status; GET/POST /led-control; POST /send-email;
GET /config/{device_id}, POST /config/{device_id}/update, POST /config/push;
GET /threshold/{device_id}, POST /threshold/{device_id}/update, POST /threshold/push.
API requests require AWS SigV4 and a caller allowed execute-api:Invoke. The current
browser does not sign requests; pointing it at this API alone will not authenticate it.
Cognito integration is not implemented. Do not disable authorization to expose the demo.

Local structural checks and cfn-lint cannot verify AWS account permissions, networking,
SES deliverability, Linux wheel builds or a successful live deployment.

## Verification

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.lock
.venv/bin/ruff check backend scripts tests
.venv/bin/python scripts/validate_config.py
.venv/bin/python -m pytest -q
```

Set TEST_DATABASE_URL only to a disposable PostgreSQL instance to run SQL integration
tests. Tests create isolated schemas and drop only those schemas. CI supplies its own
PostgreSQL service. Moto tests emulate DynamoDB; they are not AWS service tests.

## Analytics addition

The same IAM-authorized API now includes GET /analytics/summary. SensorZoneMap is
a JSON parameter matching the dashboard's current mapping by default. No schema
migration is needed for analytics. See ANALYTICS.md for query parameters, bounds,
source limitations and the unchanged browser authorization requirement.
