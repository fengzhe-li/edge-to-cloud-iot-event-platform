-- Sanitised PostgreSQL schema for the AWS IoT Smart Spill Detection System
-- Structure only: no production records, credentials, or live identifiers.
-- Target: PostgreSQL 14+

BEGIN;

CREATE TABLE public.spill_events (
    id integer NOT NULL,
    device_id integer,
    status text,
    detected_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT spill_events_status_check CHECK ((status = ANY (ARRAY['wet'::text, 'dry'::text, 'unknown'::text])))
);

CREATE TABLE public.device_heartbeats (
    device_id text NOT NULL,
    last_seen_at timestamp with time zone NOT NULL,
    last_seen_ts bigint NOT NULL,
    mqtt_topic text,
    uptime_ms bigint,
    raw jsonb NOT NULL
);

CREATE TABLE public.devices (
    id integer NOT NULL,
    name text,
    location text,
    zone_id integer,
    installed_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE public.rfid_scans (
    id bigint NOT NULL,
    device_id text NOT NULL,
    rfid_id text NOT NULL,
    rfid_uid text NOT NULL,
    scan_timestamp bigint NOT NULL,
    scanned_at timestamp with time zone NOT NULL,
    mqtt_topic text NOT NULL,
    raw jsonb NOT NULL
);

CREATE SEQUENCE public.rfid_scans_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE public.rfid_scans_id_seq OWNED BY public.rfid_scans.id;

CREATE TABLE public.sensor_config (
    device_id text NOT NULL,
    sensor_id integer NOT NULL,
    active boolean DEFAULT true NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);

CREATE TABLE public.sensor_thresholds (
    id integer NOT NULL,
    device_name character varying(100) NOT NULL,
    sensor_id integer NOT NULL,
    threshold_value integer NOT NULL,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);

CREATE SEQUENCE public.sensor_thresholds_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE public.sensor_thresholds_id_seq OWNED BY public.sensor_thresholds.id;

CREATE TABLE public.sensorstate (
    sensor_id integer NOT NULL,
    wet boolean NOT NULL,
    state text NOT NULL,
    updated_ts bigint NOT NULL,
    updated_at timestamp with time zone NOT NULL,
    last_value integer,
    mqtt_topic text,
    raw jsonb
);

CREATE SEQUENCE public.spill_events_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE public.spill_events_id_seq OWNED BY public.spill_events.id;

CREATE TABLE public.waterlevel_readings (
    id integer NOT NULL,
    received_at timestamp with time zone NOT NULL,
    received_ts bigint NOT NULL,
    mqtt_topic text NOT NULL,
    device_id character varying(100) NOT NULL,
    sensor_id integer NOT NULL,
    value integer,
    wet boolean,
    raw jsonb
);

CREATE SEQUENCE public.waterlevel_readings_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE public.waterlevel_readings_id_seq OWNED BY public.waterlevel_readings.id;

ALTER TABLE ONLY public.rfid_scans ALTER COLUMN id SET DEFAULT nextval('public.rfid_scans_id_seq'::regclass);

ALTER TABLE ONLY public.sensor_thresholds ALTER COLUMN id SET DEFAULT nextval('public.sensor_thresholds_id_seq'::regclass);

ALTER TABLE ONLY public.spill_events ALTER COLUMN id SET DEFAULT nextval('public.spill_events_id_seq'::regclass);

ALTER TABLE ONLY public.waterlevel_readings ALTER COLUMN id SET DEFAULT nextval('public.waterlevel_readings_id_seq'::regclass);

ALTER TABLE ONLY public.device_heartbeats
    ADD CONSTRAINT device_heartbeats_pkey PRIMARY KEY (device_id);

ALTER TABLE ONLY public.devices
    ADD CONSTRAINT devices_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.rfid_scans
    ADD CONSTRAINT rfid_scans_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.sensor_config
    ADD CONSTRAINT sensor_config_pkey PRIMARY KEY (device_id, sensor_id);

ALTER TABLE ONLY public.sensor_thresholds
    ADD CONSTRAINT sensor_thresholds_device_name_sensor_id_key UNIQUE (device_name, sensor_id);

ALTER TABLE ONLY public.sensor_thresholds
    ADD CONSTRAINT sensor_thresholds_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.sensorstate
    ADD CONSTRAINT sensorstate_pkey PRIMARY KEY (sensor_id);

ALTER TABLE ONLY public.spill_events
    ADD CONSTRAINT spill_events_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.waterlevel_readings
    ADD CONSTRAINT waterlevel_readings_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.spill_events
    ADD CONSTRAINT spill_events_device_id_fkey FOREIGN KEY (device_id) REFERENCES public.devices(id);

-- Apply explicitly to an existing deployment before enabling the new ingest handler.
-- Durable retry ledger; no automatic expiry. Existing history is not backfilled.
CREATE TABLE IF NOT EXISTS public.ingested_events (
    event_key text PRIMARY KEY,
    payload_hash text NOT NULL,
    processed_at timestamptz NOT NULL DEFAULT now()
);

COMMIT;
