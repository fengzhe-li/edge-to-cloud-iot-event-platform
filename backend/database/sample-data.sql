-- Fictional sample data for portfolio demonstration only.
-- Values do not represent real devices, people, RFID cards, or incidents.

BEGIN;

INSERT INTO public.spill_events (device_id, created_at)
VALUES ('demo-device-01', CURRENT_TIMESTAMP);

INSERT INTO public.device_heartbeats (device_id)
VALUES ('demo-device-01');

INSERT INTO public.devices (zone_id)
VALUES (1);

INSERT INTO public.rfid_scans (rfid_uid, device_id, scan_timestamp, scanned_at)
VALUES ('DEMO-RFID-01', 'demo-device-01', 1760000010, CURRENT_TIMESTAMP);

INSERT INTO public.sensor_config (device_id, sensor_id, updated_at)
VALUES ('demo-device-01', 0, CURRENT_TIMESTAMP);

INSERT INTO public.sensor_thresholds (sensor_id, updated_at)
VALUES (0, CURRENT_TIMESTAMP);

INSERT INTO public.sensorstate (sensor_id, state, updated_ts, updated_at)
VALUES (0, 'dry', 1760000000000, CURRENT_TIMESTAMP);

INSERT INTO public.waterlevel_readings (sensor_id, device_id)
VALUES (0, 'demo-device-01');

COMMIT;
