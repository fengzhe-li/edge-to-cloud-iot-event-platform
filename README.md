# AWS IoT Operational Analytics

[![Backend verification](https://github.com/fengzhe-li/aws-iot-operational-analytics/actions/workflows/backend.yml/badge.svg)](https://github.com/fengzhe-li/aws-iot-operational-analytics/actions/workflows/backend.yml)

A Python and PostgreSQL backend that turns IoT spill-sensor events into current
state, incident history and operational summaries. Built around AWS IoT Core,
Lambda, API Gateway, DynamoDB and SES, with a lightweight JavaScript dashboard.

This is the upgraded project. The [original repository](https://github.com/fengzhe-li/aws-iot-smart-spill-detection-system)
is preserved separately. The upgrade adds tested data-integrity behaviour and
read-only operational analytics without introducing a new streaming platform.

![System architecture](docs/images/architecture.svg)

## What the project demonstrates

- **Event processing:** classify and normalise sensor, RFID and heartbeat messages.
- **Data integrity:** transactional retry deduplication and timestamp-guarded updates
  keep historical records separate from current sensor state.
- **Operational analytics:** device health, last-seen time, reported uptime, observed
  wet transitions by sensor/device/current zone, and configurable history windows.
- **Backend interfaces:** status, configuration, threshold, actuator, email and
  analytics handlers, with a SAM template for the supported seven-function backend.
- **Engineering verification:** 102 tests passed locally, including 15 real PostgreSQL
  integration tests and four DynamoDB-emulator integration tests. GitHub Actions
  runs the suite with PostgreSQL plus lint, syntax and configuration checks.

## Analytics dashboard

The image below uses **synthetic example data**, not a live deployment or measured
production workload. The actual dashboard does not silently load sample metrics.

![Operational analytics dashboard — synthetic example data](docs/examples/analytics-dashboard.png)

`GET /analytics/summary?window_hours=24` returns:

| Area | Available information |
|---|---|
| Device health | Online/offline/unknown, quiet-but-online, last heartbeat, device-reported uptime |
| Incidents | Observed wet transitions, counts by sensor/device/current zone, transitions per hour |
| History | Recent incidents and DRY/WET/DRYING transitions, with window-boundary context |
| Configuration | Current activation state, thresholds and persisted sensor state |
| Data limitations | Explicit unavailable values for historical availability and correlated response times |

Windows can also use timezone-qualified `start` and `end`; the maximum is 31 days.
First-observed wet states and conflicting timestamps are not counted as known
incident onsets. [Metric definitions and example response →](docs/ANALYTICS.md)

## Run the checks

Use Python 3.12 for parity with CI and the Lambda runtime:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.lock
.venv/bin/ruff check backend scripts tests
.venv/bin/python -m compileall -q backend scripts tests
.venv/bin/python scripts/validate_config.py
.venv/bin/cfn-lint template.yaml
.venv/bin/python -m pytest -q
```

PostgreSQL integration tests require `TEST_DATABASE_URL` pointing to a **disposable**
database. They create and remove isolated schemas. Without it, those tests skip.
CI provides its own PostgreSQL service. AWS calls are mocked/emulated; tests do not
need production AWS credentials. The local full run used Python 3.14.5/PostgreSQL 18;
CI targets Python 3.12/PostgreSQL 16.4. The workflow badge reports GitHub run status.

## Frontend preview

```sh
cd frontend
python3 -m http.server 8000
```

Open `http://localhost:8000` and select **Open preview**. The preview gate is not
an authentication system. Cloud endpoints are placeholders, and analytics is
unconfigured by default. The supported backend requires IAM-signed requests;
the browser does not implement SigV4 or Cognito. A deployment must supply an
authorized transport or authenticated proxy—never browser AWS credentials.

## Deployment and boundaries

The root `template.yaml` describes the supported backend, shared Python layer,
IoT rules, two DynamoDB tables and IAM-authorized REST API. PostgreSQL, network
access, IoT devices and SES identity are external prerequisites.
[Deployment instructions →](docs/DEPLOYMENT.md)

- Deduplication depends on the documented event-identity contract; **exactly-once
  processing or delivery is not claimed**.
- Conditional alert state acceptance reduces duplicate attempts, but a failure
  after acceptance can lose an email notification.
- Latest-only heartbeats cannot establish historical availability. RFID scans
  lack a defensible incident acknowledgement key; response times remain unavailable.
- Configuration history and browser HANDLING state are not persisted as an audit trail.
- Legacy stored-function and EventBridge paths remain outside the supported deployment.
- No throughput, latency, high-volume capacity or production-readiness claims are made.
  The current upgraded stack has not been verified by a live AWS deployment.

The original AWS environment was decommissioned. Historical service exports are
sanitised reference material, not a complete deployment recipe.

## Repository map

```text
backend/lambda/           Python handlers, including read-only analytics
backend/layers/common/   Shared validation and structured logging
backend/database/        PostgreSQL schema and explicit migration
frontend/                Dashboard and operational analytics section
tests/unit/              Parsing, validation, aggregation and API tests
tests/integration/       PostgreSQL and DynamoDB-emulator tests
infrastructure/          Historical sanitised service exports
scripts/                 Configuration and credential-pattern checks
docs/                    Semantics, deployment, examples and engineering reports
template.yaml            Supported SAM backend
.github/workflows/       Existing backend verification workflow
```

[Engineering semantics](docs/ENGINEERING.md) · [Analytics definitions](docs/ANALYTICS.md) ·
[Implementation report](docs/IMPLEMENTATION_REPORT.md) · [Original project](https://github.com/fengzhe-li/aws-iot-smart-spill-detection-system)
