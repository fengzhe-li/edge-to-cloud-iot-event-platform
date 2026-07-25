# Email alert flow

1. A sensor event is evaluated by Lambda.
2. Wet-state events are deduplicated to avoid repeated notifications.
3. Lambda formats the operational alert.
4. Amazon SES sends the message from a verified identity.
5. Delivery, bounce, and complaint events should be monitored in production.

The portfolio copy contains no live addresses or credentials.
