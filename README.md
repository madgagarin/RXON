# RXON (Reverse Axon) Protocol

**EN** | [ES](https://github.com/madgagarin/rxon/blob/main/docs/es/README.md) | [RU](https://github.com/madgagarin/rxon/blob/main/docs/ru/README.md)

[![License: MPL 2.0](https://img.shields.io/badge/License-MPL%202.0-brightgreen.svg)](https://opensource.org/licenses/MPL-2.0)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/release/python-3110/)
[![Typing: Typed](https://img.shields.io/badge/Typing-Typed-brightgreen.svg)](https://peps.python.org/pep-0561/)

**RXON** (Reverse Axon) is a lightweight reverse-connection inter-service communication protocol designed for the **[HLN (Hierarchical Logic Network)](https://github.com/avtomatika-ai/hln)** architecture.

It serves as the "nervous system" for distributed multi-agent systems, connecting autonomous nodes (Holons) into a single hierarchical network.

## 🧬 The Biological Metaphor

The name **RXON** is derived from the biological term *Axon* (the nerve fiber). In classic networks, commands typically flow "top-down" (Push model). In RXON, the connection initiative always comes from the subordinate node (Worker/Shell) to the superior node (Orchestrator/Ghost). This is a "Reverse Axon" that grows from the bottom up, creating a channel through which commands subsequently descend.

## ✨ Key Features

-   **Pluggable Transports**: Full abstraction from the network layer. The same code can run over HTTP, WebSocket, gRPC, or Tor.
-   **Generic Event System**: Unified signaling mechanism for progress updates, custom alerts, and real-time metrics.
-   **Zero Trust Identity Chain**: Built-in support for hierarchical event bubbling with `origin_worker_id` and `bubbling_chain` to prevent spoofing in multi-layer holarchies.
-   **Detailed Resource Telemetry**: Heartbeats include granular usage metrics for CPU, RAM, and specialized hardware devices (GPU, TPU, NPU) including temperature and memory levels.
-   **Task Prioritization & Deadlines**: Built-in support for task `priority` and execution `deadline` (timestamp) to enable smart local scheduling and auto-cancellation of stale tasks.
-   **Zero Dependency Core**: The protocol core has no external dependencies (standard transports use `aiohttp` and `orjson`).
-   **Strictly Typed Contracts**: All messages (tasks, results, heartbeats) define their data structures via JSON Schemas, enabling automated validation and smart dispatching.
-   **Blob Storage Native**: Built-in support for offloading heavy data via S3-compatible storage (`rxon.blob`).

## 🏗 Architecture

The protocol is divided into two main interfaces:

1.  **Transport (Worker side)**: Interface for initiating connections, retrieving tasks, emitting events, and sending results.
2.  **Listener (Orchestrator side)**: Interface for accepting incoming connections and routing messages to the orchestration engine.

### High-Signal Telemetry (Heartbeats)

RXON Heartbeats provide the Orchestrator with a detailed view of the Holon's health:
-   `ResourcesUsage`: Real-time CPU and RAM consumption.
-   `DeviceUsage`: Per-device load, memory, and temperature for accelerators.
-   `hot_cache`: List of artifacts/models currently loaded in memory.

### Skill Contracts

Every skill declared in RXON can now include:
-   `input_schema`: JSON Schema for parameters.
-   `output_schema`: JSON Schema for results.
-   `events_schema`: Mapping of event names to their JSON Schemas.
-   `output_statuses`: List of valid logic outcomes (e.g., `success`, `retry_later`).

## 🛡️ Error Handling

RXON uses a dedicated exception hierarchy grounded in `RxonError`. It also defines standardized error codes for task results:
-   `CONTRACT_VIOLATION_ERROR`: The worker's output does not match its declared schema.
-   `DEPENDENCY_MISSING_ERROR`: A required dependency (artifact, file, service) is missing.
-   `RESOURCE_EXHAUSTED_ERROR`: Physical resources (RAM, VRAM, CPU) are exhausted.
-   `LIMIT_EXCEEDED_ERROR`: Logical limits (Quotas, Rate limits, Context windows) exceeded.
-   `TIMEOUT_ERROR`: The worker could not finish in time (or the deadline has passed).
-   `LATE_RESULT`: (Response) The orchestrator refused the result because the deadline has passed.

## 🧪 Testing

The library includes a `MockTransport` to simplify testing Workers in isolation without running a real Orchestrator.

```python
from rxon.testing import MockTransport

# Use standard factory with mock:// scheme
transport = create_transport("mock://", "test-worker", "token")
await transport.connect()

# Inject tasks directly
transport.push_task(my_task_payload)
```

## 📜 License

The project is distributed under the Mozilla Public License 2.0 (MPL 2.0).

---
*Mantra: "The RXON is the medium for the Ghost."*
