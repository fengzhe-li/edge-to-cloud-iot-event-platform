# Amazon SES infrastructure

This directory contains a sanitised portfolio export of the Amazon SES
configuration used by the AWS IoT smart spill detection system.

## Included

- Verified identity metadata where available
- Configuration-set metadata where available
- Email template metadata where available
- Sending-account and suppression configuration where available

## Sanitisation

Live email addresses, verified domains, AWS account IDs, SES ARNs, DKIM tokens,
verification tokens, SMTP credentials, access keys, and session tokens were
removed or replaced with placeholders.

## Observed resources

- Identities: See exported configuration
- Configuration sets: None found in the backup
- Templates: None found in the backup

## Architecture role

Amazon SES delivers both automatic spill alerts and manually triggered
operational notifications from Lambda functions.

## Production hardening

- Keep sender and recipient addresses in environment variables or Secrets Manager.
- Never commit SMTP credentials or DKIM verification tokens.
- Use verified identities and least-privilege `ses:SendEmail` permissions.
- Configure bounce and complaint handling.
- Apply rate limiting and alert deduplication.
- Review sandbox versus production sending status before deployment.

## Files processed

Included configuration files: 3
Skipped unsupported files: 0
