# Backend verification and reliability

## Baseline

The upgrade was developed in this separate repository, starting from commit
`cde494146bc25dd8c98542823cbcdadcebce7ac8` of the original
[aws-iot-smart-spill-detection-system](https://github.com/fengzhe-li/aws-iot-smart-spill-detection-system).
The baseline had no test suite, CI workflow or automated deployment validation.
The original repository is preserved unmodified.

## Supported data path

MQTT sensor, RFID and heartbeat messages invoke Python Lambda ingestion through
IoT rules. A PostgreSQL transaction inserts a retry-ledger entry and history/current
state changes. The status API reads current state and latest RFID scans. Config
APIs read/update thresholds and activation, then publish MQTT settings. LED commands
update DynamoDB and optionally publish MQTT. Automatic alerts use a separate
conditional DynamoDB state transition before SES delivery.

No queue/streaming platform has been added. The browser still polls REST APIs.

## Ordering and identity contract

Publisher `event_ts_ms` is preferred; `timestamp` and `ts` accept epoch seconds or
milliseconds. Without publisher time, `received_ts` is interpreted as epoch
milliseconds. With no timestamp, processing time is used and deduplication is
explicitly unavailable. Device clocks are trusted; clock skew is not corrected.
The existing history column names `received_ts`/`received_at` now contain the chosen
ordering time. The raw JSONB retains the original receipt fields.

The ledger key is a SHA-256 of device/type/event_id when supplied. Reusing an ID
with different normalized content fails. Without an event ID, a hash of normalized
content and timestamp provides best-effort deduplication. A publisher timestamp
makes MQTT redelivery with a changed IoT receipt timestamp identifiable. Receipt-only
messages with different receipt timestamps cannot be identified as duplicates.
Byte-different raw payloads with identical normalized fields are considered the same
fallback event. Identical measurements at identical timestamps can therefore collapse.
The ledger and writes commit or roll back together. Ledger rows do not expire;
retention is not implemented. Existing historical rows are not backfilled/deduplicated.

Strictly newer timestamps alone update current sensor/heartbeat state. Older events
remain in history; ties retain the first accepted current state. Sensor IDs must be
globally unique across devices, as in the existing schema. RFID scan_timestamp remains
epoch seconds for dashboard compatibility; event identity uses millisecond precision.

## Alert semantics

A consistent read plus conditional compare-and-swap accepts a new state before
sending SES email. Only the winner of a dry-to-wet transition attempts email.
Retries of the same timestamp and stale events are skipped. State-contention retries
are bounded; they do not retry SES. WET-to-WET does not send; DRYING is treated as DRY.

This is at most one application send attempt per accepted transition, NOT exactly-once
email delivery. SDK-internal retries and provider delivery behaviour remain outside
this guarantee. A crash or SES failure after the state claim can lose an alert;
retrying the event will not resend. Distinct accepted transitions may each send.
Guaranteed delivery would need a separate durable delivery workflow and is not claimed.
Legacy alert items without updated_ts fail explicitly and require an explicit migration.

## Logging and remaining boundaries

Handlers use a common layer for structured outcomes, request ID, event type/ID and
failure category. Ingestion logs its derived identity, duplicate result and state-update
outcome. API failures return generic service errors; event-handler failures propagate.
Raw events, SQL passwords and full provider errors are not logged by the wrapper.
No custom metrics, alarms, tracing or SLOs have been added.

LED persistence and MQTT publication remain non-atomic: a publish failure can leave
stored desired state ahead of the device. Config updates and publication are separate
operations, without device acknowledgements. Browser audit/assignment state is local.
No historical query API, performance benchmark or Linux systems work is claimed.

## Legacy paths

`sensor-data-processor` calls an absent `insert_sensor_json` function. Its schema/business
contract cannot be inferred safely. It now propagates failure, cleans up connections,
and forwards a compatible sensor event if persistence succeeds. It is excluded from
the supported root deployment; use database-ingest and the direct alert rule instead.
`eventbridge-email-notifier` remains an optional consumer without a publisher/rule in
this repository and is also excluded. Exported IoT rules still reference old functions;
these exports document history and must not be deployed alongside the root stack.
