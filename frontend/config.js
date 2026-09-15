/**
 * Public-safe portfolio configuration.
 *
 * Copy this file to config.local.js for a private deployment and replace the
 * placeholders there. Do not commit production endpoints, credentials, API
 * keys, client secrets, or account identifiers.
 */
window.APP_CONFIG = {
  // Full summary URL or same-origin authenticated proxy; no browser AWS credentials.
  ANALYTICS_API_BASE: "",
  STATUS_API_BASE: "https://YOUR_STATUS_API_ENDPOINT",
  EMAIL_API_BASE: "https://YOUR_EMAIL_API_ENDPOINT",
  ACTUATOR_API_BASE: "https://YOUR_ACTUATOR_API_ENDPOINT",
  IOT_API_BASE: "https://YOUR_IOT_CONFIG_API_ENDPOINT"
};
