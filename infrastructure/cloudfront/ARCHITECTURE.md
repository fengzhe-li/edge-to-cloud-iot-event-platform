# CloudFront delivery flow

1. The browser requests the dashboard through CloudFront.
2. CloudFront serves cached static assets when available.
3. Cache misses are fetched from the configured static origin.
4. HTTPS and cache policies are enforced at the distribution edge.
5. The frontend calls API Gateway separately for live application data.

This documentation intentionally excludes live domains and resource IDs.
