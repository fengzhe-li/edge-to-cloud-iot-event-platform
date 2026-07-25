# DynamoDB design notes

The DynamoDB component stores lightweight operational state that benefits from
low-latency key-value access, such as actuator state or alert deduplication.

Typical access patterns include:

1. Read the latest state by a stable partition key.
2. Update state atomically after a control action.
3. Check whether an alert has already been sent for a recent event.
4. Expire short-lived records with TTL where applicable.

Relational event history remains in PostgreSQL, while DynamoDB is used for
small, high-frequency operational state.
