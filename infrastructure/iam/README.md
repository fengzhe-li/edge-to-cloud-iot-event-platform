# AWS IAM infrastructure

This directory contains a sanitised portfolio export of the IAM roles and
policies used by the AWS IoT smart spill detection system.

## Included

- Role metadata and trust policies
- Inline and attached policy documents
- Service permissions used by Lambda and related AWS services
- High-level least-privilege review notes

## Sanitisation

Live AWS account IDs, ARNs, role/policy identifiers, access keys, session
tokens, passwords, and credential-like values were removed or replaced with
placeholders.

## Observed resources

### Roles

- `AWSServiceRoleForAPIGateway`
- `AWSServiceRoleForAmazonSES`
- `AWSServiceRoleForCloudFrontLogger`
- `AWSServiceRoleForLambdaReplicator`
- `AWSServiceRoleForRDS`
- `AWSServiceRoleForResourceExplorer`
- `AWSServiceRoleForSupport`
- `AWSServiceRoleForTrustedAdvisor`
- `AlertNotificationServiceauto-role-j961wplw`
- `EdgeCognitoGate-role-hqzjhw6s`
- `LEDfunction-role-m0hn3sdl`
- `ManualEmailSender-role-cetq0bk4`
- `PushSensorConfig-role-771csnrf`
- `PushSensorConfig-role-h9c24z30`
- `PushSensorConfig-role-rd1ttmyu`
- `SensorDataProcessor-role-ppoflq8w`
- `SensorThreshold-role-lw8cr2s3`
- `SpillAlertMailer-role-mgln7ci3`
- `SpillEmailNotifier-role-u8gyjfti`
- `StatusApiLambda-role-fma7tqtg`
- `database-role-zkjrhvd2`
- `databaseconnection-role-urnwaek2`
- `databasesave-role-8o38ptl2`
- `databasesave-role-p0rcizby`
- `email_function-role`
- `email_function-role-q0tg0qcn`
- `lambda-s3-email-role`
- `mqttToDB-role-44zrz9eh`
- `mqttToDB2-role-ehr29pxs`

### Policies

- `APIGatewayServiceRolePolicy`
- `AWSCloudFrontLogger`
- `AWSLambdaBasicExecutionRole-01ffbf1e-e770-429d-ab7c-94f51de251d3`
- `AWSLambdaBasicExecutionRole-18d16f4e-dfa3-4127-af50-9297d23cac4d`
- `AWSLambdaBasicExecutionRole-293a0adc-630d-4962-823c-6cc0d304a4e9`
- `AWSLambdaBasicExecutionRole-3434ead7-6ee1-4a89-9094-ba02752bea2d`
- `AWSLambdaBasicExecutionRole-3e893366-0229-478a-b2cd-5b474ecf5bdf`
- `AWSLambdaBasicExecutionRole-45d60353-c5a2-483e-b563-9e20f692c607`
- `AWSLambdaBasicExecutionRole-4acbc291-8924-4d83-b6fb-db605b5e25cc`
- `AWSLambdaBasicExecutionRole-4d28bee4-f1c6-4dc1-9e88-5b7bb095c29a`
- `AWSLambdaBasicExecutionRole-65383136-b58c-40a6-ba60-8ef3edb4daf6`
- `AWSLambdaBasicExecutionRole-9a44c7ac-7b8a-4a24-9c54-37c41eb27c75`
- `AWSLambdaBasicExecutionRole-9ff73a32-0418-465a-8b62-2f6202fb0162`
- `AWSLambdaBasicExecutionRole-a9ee3cdb-ae69-4a55-b13d-e5a67d0ec21d`
- `AWSLambdaBasicExecutionRole-b00ecd26-a26e-4475-b892-d64cba5265af`
- `AWSLambdaBasicExecutionRole-bde3abe1-4679-4cec-896c-f59876225b69`
- `AWSLambdaBasicExecutionRole-cb2bb519-445a-499f-82ac-e14ad6af22d4`
- `AWSLambdaBasicExecutionRole-d83885cd-2978-445b-a0bd-fdcaecdbf067`
- `AWSLambdaBasicExecutionRole-de23081f-ed4b-4eb0-befe-a4097f07da97`
- `AWSLambdaBasicExecutionRole-e72b6c28-3848-495b-991a-bfffebc4a741`
- `AWSLambdaBasicExecutionRole-fd402a2e-7833-4a33-b6f7-d11fb3eb687d`
- `AWSLambdaDynamoDBExecutionRole`
- `AWSLambdaReplicator`
- `AWSLambdaRole`
- `AWSResourceExplorerServiceRolePolicy`
- `AWSSupportServiceRolePolicy`
- `AWSTrustedAdvisorServiceRolePolicy`
- `AllowInvokeMailLambda`
- `AllowSESAccess`
- `AllowSESSendEmail`
- `AmazonEventBridgeFullAccess`
- `AmazonRDSServiceRolePolicy`
- `AmazonS3FullAccess`
- `AmazonSESFullAccess`
- `AmazonSESServiceRolePolicy`
- `Auto312`
- `CloudWatchLogsFullAccess`
- `EdgeLambdaLogsPolicy`
- `EmailSend`
- `IoTPublishConfig`
- `LEDfunctionDynamoDBAccess`
- `LambdaIoTPublish`
- `changeAUTOemail`

### AWS services referenced by policy actions

- `dynamodb`
- `events`
- `iot`
- `lambda`
- `logs`
- `ses`
- `sts`

## Security recommendations

- Scope actions and resources to the minimum required.
- Avoid `Action: "*"` and broad service wildcards.
- Separate execution roles by Lambda responsibility.
- Keep trust policies restricted to required AWS services.
- Do not commit credentials or user access-key material.
- Review unused roles and policies before deployment.
