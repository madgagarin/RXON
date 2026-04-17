# RXON (Reverse Axon) Protocol

**EN** | [ES](https://github.com/madgagarin/rxon/blob/main/docs/es/README.md) | [RU](https://github.com/madgagarin/rxon/blob/main/docs/ru/README.md)

[![License: MPL 2.0](https://img.shields.io/badge/License-MPL%202.0-brightgreen.svg)](https://opensource.org/licenses/MPL-2.0)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/release/python-3110/)
[![PyPI version](https://img.shields.io/pypi/v/rxon.svg)](https://pypi.org/project/rxon/)

**RXON** (Reverse Axon) is a lightweight, extensible reverse-connection protocol designed for **[HLN (Hierarchical Logic Network)](https://github.com/avtomatika-ai/hln)** architectures.

It serves as the "nervous system" for distributed multi-agent systems, providing a strictly typed, Zero Trust foundation for inter-service communication.

## 🚀 Concept

In traditional networks, commands usually flow "top-down" (Push model). In **RXON**, the connection initiative always comes from the subordinate node (Shell) to the superior node (Orchestrator). This "Reverse Axon" architecture allows workers to operate behind NAT or Firewalls without complex network configuration, while maintaining a secure, bi-directional control channel.

## ✨ Key Features

-   **Reverse Connection (PULL)**: Nodes connect to the orchestrator to pull tasks, ensuring compatibility with complex network environments.
-   **Zero Trust Security**: Built-in support for digital signatures (`SecurityContext`) and identity chains. All messages use strictly integer timestamps for cryptographic stability and can be verified across multiple holarchy layers.
-   **Agnostic & Extensible**: Core models (Resources, Skills, Tasks) are fully extensible via universal `metadata` and `properties` fields. `TaskResult` supports `origin_worker_id` for transparent traceability in deep holarchies.
-   **Universal Telemetry**: Heartbeats include granular metrics for CPU, RAM, and any custom devices (Sensors, GPUs, Actuators) via the extensible `HardwareDevice` model.
-   **Generic Event System**: Unified signaling for progress updates, custom alerts, and real-time triggers with hierarchical event bubbling.
-   **Smart Resource Matching**: Formalized logic for hardware requirements using **GE (Greater or Equal)** logic for numbers and partial string matching for models.
-   **Pluggable Blob Storage**: Standardized `BlobProvider` interface for offloading heavy data via S3, GCS, or Local storage to keep the control channel lightweight.
-   **Unified Factory**: Easy transport initialization via `create_transport` supporting `http://`, `https://`, `ws://`, and `wss://` schemes.
-   **Zero Dependency Core**: The protocol core is written in pure Python 3.11+. Standard transports use `aiohttp` and `orjson` for peak performance.

## 🏗 Architecture

The protocol is divided into two main interfaces:

1.  **Transport (Worker side)**: For initiating connections, retrieving tasks, emitting events, and sending results.
2.  **Listener (Orchestrator side)**: For accepting incoming connections and routing messages to the engine.

### Smart Dispatching Logic

RXON formalizes the rules for matching tasks to holons:
1.  **Identity Match**: Direct match by device ID.
2.  **Type & Model Match**: Exact match by type, partial match by model string (case-insensitive).
3.  **Property Match (Smart Comparison)**:
    *   **Numbers**: Checked as **at least** (Worker value >= Requirement).
    *   **Others**: Checked as strict equality.

## 🛡️ Error Handling

RXON defines a set of standardized, cross-platform error codes to ensure consistent behavior across different implementations:
-   `CONTRACT_VIOLATION_ERROR`: Data does not match the negotiated schema.
-   `SECURITY_ERROR`: Authentication or signature verification failed.
-   `RESOURCE_EXHAUSTED_ERROR`: Physical resources (RAM, VRAM) are insufficient.
-   `DEPENDENCY_ERROR`: A required service or artifact is unavailable.

## 🧪 Quick Start

```python
from rxon import create_transport
from rxon.models import Resources, HardwareDevice, WorkerRegistration

# 1. Create transport (supports http, https, ws, wss)
transport = create_transport("ws://api.hln.local", "worker-01", "secret-token")

# 2. Define worker resources
my_res = Resources(
    cpu_cores=8,
    devices=[HardwareDevice(type="gpu", model="RTX 4090", properties={"memory_gb": 24})]
)

# 3. Smart Matching Logic
req = Resources(cpu_cores=4, devices=[HardwareDevice(type="gpu", properties={"memory_gb": 16})])
if my_res.matches(req):
    print("This holon is ready for the task!")
```

## 📜 License

The project is distributed under the Mozilla Public License 2.0 (MPL 2.0).

---
*Mantra: "The RXON is the medium for the Ghost."*
