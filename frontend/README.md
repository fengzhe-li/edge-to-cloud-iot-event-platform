# Frontend dashboard

This directory contains the sanitised portfolio version of the SensorWatch
dashboard.

## Run locally

Serve the directory with a local web server, for example:

```bash
python3 -m http.server 8000
```

Then open `http://localhost:8000`.

Select **Open preview**; there is no password.

## Configuration

`config.js` contains placeholder API endpoints only. For a private deployment,
replace them locally and do not commit production endpoints, credentials,
account IDs, API keys, certificates, client secrets, or real user data.


The password comparison has been removed. Open preview is a local UI gate only.
The supported backend requires IAM-signed requests; this frontend does not sign
requests or implement Cognito. Full browser authentication remains out of scope.
