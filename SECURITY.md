# Security Policy

**EN** | [ES](https://github.com/madgagarin/rxon/blob/main/docs/es/SECURITY.md) | [RU](https://github.com/madgagarin/rxon/blob/main/docs/ru/SECURITY.md)

## Reporting a Vulnerability

Please report security issues or vulnerabilities to [madgagarin@gmail.com].

## Security Architecture

RXON enforces security boundaries for distributed execution across HLN networks:

### Digital Signatures and HMAC

The protocol supports payload signing via HMAC-SHA256 (symmetric) and Ed25519 (asymmetric) (`security.signature`):

- **Integrity**: Payloads cannot be altered in transit.
- **Authenticity**: Only endpoints holding valid signing keys or shared secrets can emit authoritative commands or results.
- **Canonical serialization**: Canonical JSON encoding via `orjson` ensures identical byte sequences for signature verification.

### Replay Protection

Signed payloads require an integer `timestamp`. The orchestrator rejects messages that:

- Are older than the configured time window (60 seconds by default).
- Contain timestamps set in the future beyond allowed drift.
- Replay an already processed `event_id` or `task_id` within the active validity window.

### Identity and Call Chains

Events emitted from subordinate nodes contain `origin_worker_id` and `bubbling_chain`. The cryptographic signature covers the message payload and call hierarchy, preventing identity spoofing without access to the secret key.

### Interface Contracts and Schema Validation

Protocol messages (worker registration, heartbeats, skill definitions, task payloads) are validated against JSON Schemas:

- Input and output schemas use `additionalProperties: False` to reject unknown fields and prevent state injection.
- Invalid payloads are rejected before task execution begins.

### Reverse Connection Model

Connections are established outbound from worker nodes to orchestrators. Workers do not expose public listening ports, reducing attack surface against unsolicited inbound traffic.

### Task Assignment and Deadlines

Task execution results are validated against the worker assigned to the task ID. Optional `deadline` timestamps enforce execution timeouts and prevent late processing of stale jobs.

### Resource Telemetry

Heartbeat telemetry reports memory, GPU, and CPU utilization, allowing orchestrators to detect overload conditions and route tasks away from saturated nodes.
