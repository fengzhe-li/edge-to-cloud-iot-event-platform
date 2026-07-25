# Frontend dashboard

This directory contains the sanitised portfolio version of the SensorWatch
dashboard.

## Run locally

Serve the directory with a local web server, for example:

```bash
python3 -m http.server 8000
```

Then open `http://localhost:8000`.

The demonstration password is `demo`.

## Configuration

`config.js` contains placeholder API endpoints only. For a private deployment,
replace them locally and do not commit production endpoints, credentials,
account IDs, API keys, certificates, client secrets, or real user data.

The password screen is a UI demonstration and is not secure authentication.
A production deployment should use server-side sessions or an identity provider
such as Amazon Cognito.
