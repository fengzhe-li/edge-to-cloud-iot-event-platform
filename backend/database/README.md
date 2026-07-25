# PostgreSQL database

This directory contains a public-safe database representation for the AWS IoT
smart spill detection system.

## Files

- `schema.sql` — PostgreSQL table, sequence, index, and constraint definitions
- `sample-data.sql` — a small fictional dataset for local demonstration

## Core model

The schema contains 8 application tables:

- `spill_events`
- `device_heartbeats`
- `devices`
- `rfid_scans`
- `sensor_config`
- `sensor_thresholds`
- `sensorstate`
- `waterlevel_readings`

Together they represent device registration and heartbeats, current sensor
state, historical water-level readings, spill events, RFID scans, and per-device
configuration and thresholds.

## Local setup

```bash
createdb spill_demo
psql spill_demo < schema.sql
psql spill_demo < sample-data.sql
```

The sample data is fictional and contains no production device identifiers,
personal data, live RFID values, email addresses, or operational history.

## Security

Do not commit full PostgreSQL dumps or custom-format `.backup` files. Store
production credentials in AWS Secrets Manager or SSM Parameter Store and use a
least-privilege database role for Lambda access.
