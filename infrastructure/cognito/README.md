# Amazon Cognito infrastructure

This directory contains a sanitised portfolio export of the Cognito resources
associated with the AWS IoT smart spill detection system.

## Included

- User pool metadata where available
- App client configuration where available
- Password, MFA, and token settings where available
- Hosted UI/domain metadata where available

## Sanitisation

Live user-pool IDs, app-client IDs, domains, AWS account IDs, ARNs, client
secrets, and user records were removed or replaced with placeholders.

## Observed resources

- User pool names: User pool - glhfgx, address, birthdate, email, email_verified, family_name, gender, given_name, identities, locale, middle_name, name, nickname, phone_number, phone_number_verified, picture, preferred_username, profile, sub, updated_at, verified_email, verified_phone_number, website, zoneinfo
- App client names: SpillingDetection

## Production hardening

- Never commit app-client secrets.
- Enable MFA where appropriate.
- Use short-lived tokens and least-privilege scopes.
- Restrict callback and logout URLs to trusted origins.
- Avoid storing user exports in source control.
- Use Cognito groups or custom claims only when required.

## Files processed

Included configuration files: 5
Skipped unsupported files: 0
