# Amazon CloudFront infrastructure

This directory contains a sanitised portfolio export of the CloudFront
distribution used to deliver the web dashboard.

## Included

- Distribution configuration
- Origin configuration
- Cache behaviours
- Viewer protocol policy
- Error response configuration
- Compression and price-class settings where present

## Sanitisation

Live distribution IDs, CloudFront domain names, AWS account IDs, S3 origin
domains, ARNs, and credential-like values were replaced with placeholders.

## Architecture role

CloudFront sits in front of the static frontend origin and provides global
content delivery, HTTPS termination, caching, and browser-facing delivery of the
dashboard.

## Observed configuration summary

- Origins: EXAMPLE.cloudfront.net, example-bucket.s3.eu-north-1.amazonaws.com
- Default root objects: index.html
- Viewer protocol policies: redirect-to-https
- Price classes: PriceClass_All

## Production hardening

- Use Origin Access Control for private S3 origins.
- Redirect HTTP traffic to HTTPS.
- Restrict allowed methods to those actually required.
- Enable access logging where appropriate.
- Keep custom-domain and certificate values outside source control.
- Avoid caching sensitive API responses.
