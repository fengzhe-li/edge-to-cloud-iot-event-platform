# Backend improvement report

## Scope and baseline

Base commit: cde494146bc25dd8c98542823cbcdadcebce7ac8 of the original
[aws-iot-smart-spill-detection-system](https://github.com/fengzhe-li/aws-iot-smart-spill-detection-system)
repository. The original repository was not modified.
Baseline: no tests, CI or automated configuration validation.

## Verification results

Counts below are from the time of this report. The README gives the current
suite size.

- 56 unit tests passed, including all eight handler imports with safe test configuration.
- 8 real PostgreSQL integration tests passed: ordering, ties, history persistence,
  duplicate ingestion, concurrent duplicates, conflicting IDs, RFID and rollback.
- 4 Moto DynamoDB integration tests passed: transitions, stale events, concurrent
  duplicates, DRYING resets and ambiguous send failure semantics.
- Total: 68 passed, zero skipped in the final full run.
- Local environment: Python 3.14.5, PostgreSQL 18 (isolated instance).
- Ruff E9/F lint, Python compileall, dependency consistency and JS syntax checks passed.
- Offline JSON/SAM path checks and cfn-lint 1.39.0 root-template validation passed.
- Targeted credential-pattern check passed. This does not prove absence of every secret.
- No type checker introduced, no performance benchmarks, no live AWS tests/deployment.
- CI is configured for Python 3.12/PostgreSQL 16.4 but has not run on GitHub here.

## Bugs and reliability changes

- Added missing os import to manual-email handler; corrected sender configuration.
- Enforced API methods and added GET to LED OpenAPI export.
- Corrected sensor-config IoT endpoint usage and strict boolean/integer validation.
- Removed legacy processor false success after failed database writes or invocation.
- Legacy processor now forwards sensor payloads, including dry transitions, rather than
  an incompatible email-shaped object. Its missing stored function remains unresolved.
- Fixed current-state regression from older sensor and heartbeat events.
- Added transactional event ledger; duplicate retries do not insert duplicate history
  within the documented identity contract. Different payloads reusing an ID fail.
- Replaced alert read-send-write with conditional state acceptance before SES.
- Standardized handler outcomes/error categories/request IDs, with redacted API failures.
- Corrected CodeUri paths; added shared-layer paths and root supported deployment.
- Removed frontend demonstration password and documented preview/auth boundary.

## Deployment and CI

Root SAM covers six supported handlers, shared layer, IoT rules, IAM-protected REST
API and two DynamoDB tables. Existing PostgreSQL/network/SES/device prerequisites
remain external. Historical function/config exports are not a deployment recipe.
GitHub Actions installs locked dependencies, checks syntax/imports, lint, config,
SAM/CloudFormation structure and credential patterns, then runs the full suite with
an isolated PostgreSQL service. No AWS credentials are required by tests.

## Remaining gaps

- Legacy insert_sensor_json definition and business contract remain absent; legacy
  processor is excluded from supported deployment. EventBridge consumer is unwired.
- Claim-before-send may lose alerts on crash/send failure. No exactly-once delivery,
  durable outbox, DLQ, replay or guaranteed notification recovery.
- Receipt-only redeliveries with changed timestamps are not deduplicated. Identical
  fallback identities collapse; no ledger retention/backfill; device clocks are trusted.
- Current sensor IDs must be globally unique across devices.
- LED state/MQTT publish and config update/push are not atomic or device-acknowledged.
- Browser cannot sign the new IAM API. Cognito integration is not implemented.
- Browser audit/assignment state is local; no historical-query endpoint.
- Existing frontend sensor-zero assignment guards use truthiness, which can prevent
  assignment/reopening for sensor 0; this frontend workflow is outside the backend work.
- No application metrics/alarms, distributed tracing, SLO, load/latency benchmarks,
  live deployment verification, Linux/system-level work or high-volume evidence.

## Claims boundary

Safe: tested Python backend; event-driven ingestion; relational modelling; transactional
retry deduplication within stated limits; timestamp ordering; conditional state transitions;
structured logs; configured CI; statically validated deployment template.

Not safe: exactly-once, guaranteed alert delivery, production-grade, highly available,
high-throughput, low-latency, measured scalability, deployed secure browser authentication,
complete streaming/replay platform, live GitHub CI success or verified AWS deployment.

## Changed files

- `.github/workflows/backend.yml`
- `.gitignore`
- `README.md`
- `backend/database/migrations/001_event_ledger.sql`
- `backend/database/schema.sql`
- `backend/lambda/.env.example`
- `backend/lambda/README.md`
- `backend/lambda/automatic-alert/lambda_function.py`
- `backend/lambda/automatic-alert/template.yaml`
- `backend/lambda/database-ingest/lambda_function.py`
- `backend/lambda/database-ingest/requirements.txt`
- `backend/lambda/database-ingest/template.yaml`
- `backend/lambda/eventbridge-email-notifier/lambda_function.py`
- `backend/lambda/eventbridge-email-notifier/template.yaml`
- `backend/lambda/led-control/lambda_function.py`
- `backend/lambda/led-control/template.yaml`
- `backend/lambda/manual-email-sender/lambda_function.py`
- `backend/lambda/manual-email-sender/template.yaml`
- `backend/lambda/sensor-config/lambda_function.py`
- `backend/lambda/sensor-config/requirements.txt`
- `backend/lambda/sensor-config/template.yaml`
- `backend/lambda/sensor-data-processor/lambda_function.py`
- `backend/lambda/sensor-data-processor/requirements.txt`
- `backend/lambda/sensor-data-processor/template.yaml`
- `backend/lambda/status-api/lambda_function.py`
- `backend/lambda/status-api/requirements.txt`
- `backend/lambda/status-api/template.yaml`
- `backend/layers/common/python/spill_common.py`
- `docs/DEPLOYMENT.md`
- `docs/ENGINEERING.md`
- `docs/IMPLEMENTATION_REPORT.md`
- `frontend/README.md`
- `frontend/app.js`
- `frontend/config.js`
- `frontend/index.html`
- `infrastructure/api-gateway/led-control-api.openapi.json`
- `infrastructure/cognito/AUTH-FLOW.md`
- `pyproject.toml`
- `requirements-dev.lock`
- `requirements-dev.txt`
- `scripts/check_secrets.py`
- `scripts/validate_config.py`
- `template.yaml`
- `tests/conftest.py`
- `tests/integration/test_alert.py`
- `tests/integration/test_postgres.py`
- `tests/unit/test_api.py`
- `tests/unit/test_ingestion.py`
- `tests/unit/test_logging.py`
