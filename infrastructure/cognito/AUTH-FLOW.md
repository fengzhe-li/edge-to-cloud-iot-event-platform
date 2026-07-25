# Suggested authentication flow

1. The user signs in through Amazon Cognito.
2. Cognito returns ID and access tokens to the frontend.
3. The frontend sends the access token in the `Authorization` header.
4. API Gateway validates the token with a Cognito or JWT authorizer.
5. Lambda receives only authorised requests.

The original frontend password screen was a UI demonstration and should not be
used as production authentication.
