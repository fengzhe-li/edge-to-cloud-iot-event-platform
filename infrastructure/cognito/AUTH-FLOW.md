# Authentication boundary

Cognito exports preserve prior configuration, not an implemented application login.
The dashboard has an explicit local preview gate and contains no password comparison.
The supported root SAM backend requires AWS IAM/SigV4 authorization on its REST API.
The browser does not obtain Cognito tokens or sign requests. Historical OpenAPI exports
lack authorizers and must not be treated as secure deployment templates.

A complete browser authentication flow remains out of scope. Do not put AWS keys in
frontend configuration or expose historical unauthenticated APIs for the demo.
