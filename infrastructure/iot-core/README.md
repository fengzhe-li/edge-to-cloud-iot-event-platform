# AWS IoT Core infrastructure

This directory contains a sanitised portfolio export of the IoT Core resources
used by the smart spill detection system.

## Included

The backup contained configuration for IoT things, policies, rules, and related
resource metadata. Live AWS account IDs, IoT endpoints, device identifiers,
certificate IDs, and ARNs have been replaced with placeholders.

## Excluded

Certificates, private keys, public keys, and other credential material are
intentionally excluded from this repository.

## Security notes

- Never commit `.pem`, `.crt`, `.key`, `.p12`, or `.pfx` files.
- Use least-privilege IoT policies.
- Restrict MQTT topics to specific device namespaces.
- Rotate certificates when a device is decommissioned.
- Store production endpoints and identifiers outside source control.

## Files processed

Included configuration files: 31
Excluded credential or unsupported files: 1
