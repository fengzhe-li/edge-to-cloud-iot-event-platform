# AWS IoT Smart Spill Detection System

A serverless AWS IoT system that processes sensor data, detects water spills,
stores operational events, triggers alerts, and visualises incidents through a
web dashboard.

## Architecture

```text
IoT sensors
   ↓ MQTT
AWS IoT Core
   ↓ IoT Rules
AWS Lambda
   ├── PostgreSQL / Amazon RDS
   ├── Amazon DynamoDB
   ├── Amazon SES
   └── API Gateway
            ↓
      Web dashboard
      S3 + CloudFront
```

## Features

- Live monitoring of six spill sensors across three supermarket zones
- Wet/dry state detection and operational event logging
- Device-heartbeat and RFID scan processing
- Automatic and manual email alerts
- Remote LED actuator control
- Sensor activation and threshold configuration
- PostgreSQL history with DynamoDB operational state
- Static dashboard delivery through S3 and CloudFront

## Technology stack

- **Cloud:** AWS IoT Core, Lambda, API Gateway, RDS PostgreSQL, DynamoDB,
  SES, S3, CloudFront, Cognito, IAM and CloudWatch
- **Backend:** Python
- **Frontend:** HTML, CSS and JavaScript
- **Database:** PostgreSQL
- **Interfaces:** MQTT and REST/OpenAPI

## Repository structure

```text
frontend/                 Sanitised dashboard
backend/
  lambda/                 Lambda functions
  database/               PostgreSQL schema and fictional samples
infrastructure/
  api-gateway/            OpenAPI exports
  iot-core/               Things, policies and rules
  dynamodb/               Table definitions
  cloudfront/             Distribution configuration
  cognito/                Authentication configuration
  iam/                    Sanitised role and policy exports
  ses/                    Email-service configuration
docs/                     Architecture and project documentation
```

## Running the frontend

```bash
cd frontend
python3 -m http.server 8000
```

Open `http://localhost:8000`. The portfolio demonstration password is `demo`.

The public configuration contains placeholder API endpoints, so cloud-backed
features require a private deployment configuration.

## Database setup

```bash
createdb spill_demo
psql spill_demo < backend/database/schema.sql
psql spill_demo < backend/database/sample-data.sql
```

## Security

This is a sanitised portfolio copy. It contains no production credentials,
private keys, certificates, full database dumps, CloudWatch logs, live API IDs,
or operational user data.

The frontend password screen is only a UI demonstration. A production version
should use Cognito/JWT authentication, Secrets Manager, restricted CORS,
least-privilege IAM and private database networking.

## Project status

The original AWS environment was backed up and decommissioned to avoid ongoing
cloud charges. This repository preserves the architecture, application code,
schema and infrastructure configuration for technical review.
