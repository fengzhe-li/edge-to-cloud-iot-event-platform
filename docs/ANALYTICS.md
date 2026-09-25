# Operational analytics

This addition reads existing PostgreSQL tables through one Python Lambda. It does
not change ingestion, deduplication, event ordering, alert handling or their tests.
The root SAM template adds the Lambda behind the existing IAM-authorized REST API,
using the existing common layer and database network parameters. No new database
schema, infrastructure service or dependency is required.

## API

`GET /analytics/summary?window_hours=24`

Alternatively, use both `start` and `end`, e.g.
`/analytics/summary?start=2026-09-05T12:00:00Z&end=2026-09-06T12:00:00Z`.
Timestamps must include a timezone. Windows are start-inclusive/end-exclusive,
positive, no longer than 31 days, and cannot end in the future. Default: 24 hours.
Do not combine the two query forms. Unknown parameters are rejected.

The query runs in a read-only, repeatable-read transaction with a five-second
per-statement timeout. More than 10,000 selected readings, including boundary
context, returns 422 instead of silently calculating truncated counts. This is a
safety bound, not a performance benchmark. Queries may still scan older history
for baseline/latest readings; indexing and high-volume performance are not validated.
Recent lists are limited to 20 incidents and 50 transitions; total counts describe
the complete accepted window. Very large fleet configuration lists are not paginated.

## Data and metric definitions

| Source | Output | Boundary |
|---|---|---|
| device_heartbeats | Current online/offline/unknown, last-seen, heartbeat age, reported uptime | Only latest heartbeat exists; no historical availability percentage |
| waterlevel_readings | Observed wet transitions by sensor/device/current zone, recent incidents, transitions/hour | Repeated WET readings are not additional incidents |
| sensorstate | Current persisted state and timestamp | Current snapshot, not window-end state |
| rfid_scans | Scan count in window | No defensible incident/acknowledgement join |
| sensor_config / sensor_thresholds | Current activation and thresholds | No historical configuration versions |
| spill_events + devices | Separate recent legacy records with relational zone | No sensor key; timezone-naive dates; not merged into window incident metrics |

Health is calculated at generated_at, independently of the requested history window.
A heartbeat age from zero through HEARTBEAT_TIMEOUT_SECONDS (default 60) means
online. Older means offline. Missing/future heartbeat means unknown. A device with
a fresh heartbeat but no recent sensor reading is quiet-but-online. Offline here
means heartbeat timeout, not proof of physical failure. Reported uptime is the
last device-provided uptime_ms counter, not server-measured availability; it is not
extrapolated. Only devices observed in heartbeats/readings/configuration are listed.
No data means an empty/unknown result, not a healthy system.

An observed incident is a recorded DRY/DRYING-to-WET transition in event-time order.
One complete final timestamp group before the window establishes each sensor's
boundary state. A first-observed WET without a known preceding dry state is listed
separately and excluded from incident_count and events_per_hour. Conflicting states
at one timestamp are marked ambiguous; onsets involving that group are excluded.
Raw DRYING is retained where available; UNKNOWN is never treated as known dry.
Counts are observed transitions, not independently confirmed physical spills.
Missing events, inaccurate device clocks and historical data quality can affect them.

The ordering timestamp is waterlevel_readings.received_ts: newer ingestion chooses
publisher time when present and receipt time otherwise. Older records may use receipt
time. Dates are not reinterpreted to manufacture a different event timeline.

SENSOR_ZONE_MAP is an explicit JSON sensor-to-zone map. The root template's default
matches the existing dashboard: 0/1→1, 2/5→2, 3/4→3. It is current configuration,
not evidence of historical location. Unmapped sensors stay unmapped. Standalone
handler imports default to an empty map. Sensor IDs are assumed globally unique
for zone attribution, matching the existing project contract. Device/sensor history
is still grouped by both fields. No integer devices.id-to-text device ID join is invented.

## Unsupported metrics and configuration audit decision

Response-time mean is null and supported=false. RFID identifies a scan and device,
but not which incident it acknowledged; browser staff handling/assignment is not
persisted as a correlated event. Nearest-timestamp matching would invent a response
relationship. HANDLING history is therefore not claimed.

Availability percent is null because heartbeat history is overwritten. A device's
uptime counter cannot determine window availability or reconstruct outages/restarts.

Current configuration timestamps are returned as stored_updated_at, not a change
history: the activation writer does not reliably update that field, and threshold
timestamps are timezone-naive. A prospective transactional audit could be useful,
but would need a schema migration and changes to configuration writers, plus a clear
actor/version contract. It cannot recover past changes. This read-only analytics
phase deliberately leaves those completed handlers unchanged and exposes no fabricated
audit history. No new audit record is added.

Legacy spill rows are exposed separately (latest 20 by ID, not window-filtered).
Their device foreign key supports a zone join, but dates lack timezone and records
lack a sensor key. Combining them with reading-derived incidents risks double counting.

## Dashboard and security

The existing dashboard adds a compact section with a window selector and manual
refresh. It shows device health, observed incident counts, zone counts, recent
incidents/transitions, response-time limitations, current sensor state and settings.
All returned text is inserted with textContent. Loading/errors hide previous results;
requests have a ten-second client timeout. No automatic extra polling is added.

ANALYTICS_API_BASE is the full summary URL or an existing same-origin authenticated
proxy path. It defaults to empty; the UI never silently substitutes sample data.
The new endpoint inherits AWS_IAM from the existing API. The browser still has no
SigV4/Cognito implementation. A deployment may provide window.analyticsFetch as its
existing authorized fetch transport. No such auth transport/proxy is implemented here,
and no browser AWS credentials or public API bypass are introduced. Ordinary fetch
works only where the deployment already supplies appropriate authorization/access.

## Examples and verification

[Example JSON](examples/analytics-summary.json) is a synthetic, abbreviated response
for documentation, not a production observation. The screenshot uses that fixture:

![Analytics section with explicitly synthetic data](examples/analytics-dashboard.png)

Added tests: 27 unit tests and 7 real PostgreSQL integration tests (34 total).
The existing pytest discovery and GitHub Actions PostgreSQL service run them without
a second CI system. Final Python suite: 102 passed, zero skipped with the isolated
database; 83 unit, 15 PostgreSQL integration and 4 Moto integration tests.
Ruff, compileall, JSON/SAM checks, cfn-lint and JS syntax pass. A separate headless
browser smoke check verified rendering, unavailable metrics, mobile section width
and failure state; it is not counted in the Python total or claimed as CI browser coverage.
GitHub-hosted CI and live AWS deployment were not run during this change.
