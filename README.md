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

-   **Reverse Connection (PULL)**: Nodes connect to the orchestrator to pull tasks, ensuring compatibility with complex network environments (NAT/Firewalls).
-   **Zero Trust Security**: Payload signing via HMAC-SHA256 with constant-time verification. Support for identity chains and mTLS certificate identity extraction.
-   **Deep Model Restoration**: Robust `from_dict` utility that recursively restores complex Python types (NamedTuples, Dataclasses, Enums, UUIDs) from raw dictionaries, supporting nested structures and `Union` types.
-   **Secure Serialization**: `to_dict` utility that recursively strips `None` values to reduce payload size and normalizes `float` values (e.g., `1.0` -> `1`) to ensure stable cryptographic hashes.
-   **Automated Contract Validation**: Built-in JSON Schema engine that automatically infers schemas from Python types and validates `TaskPayload` parameters against `SkillInfo` contracts.
-   **Advanced Resource Matching**: Mathematical logic for resource allocation:
    *   **Numbers**: Uses **GE (Greater or Equal)** logic (Requirement <= Available).
    *   **Lists**: Uses **Inclusion** (val in list) or **Intersection** (any common element).
    *   **Strings**: Case-insensitive partial matching for hardware models.
-   **Unified Telemetry**: Heartbeats include granular metrics for any custom devices (Sensors, GPUs, Actuators) and generic system properties via the extensible `HardwareDevice` model.
-   **Resilient Transport**: HTTP/WebSocket implementation with automatic token refresh (STS), exponential backoff for reconnections, and graceful session closing.

## 🏗 Architecture & Logic

### Internal Validation & Normalization
The library ensures data integrity at several layers:
1.  **Serialization Stability**: When signing messages, RXON normalizes all numeric types and sorts dictionary keys to ensure the same object always produces the same HMAC hash regardless of minor formatting differences.
2.  **Recursion Protection**: All recursive operations are limited to a depth of 100 to prevent stack overflow or DoS attacks via malicious payloads.
3.  **Schema Enforcement**: Before task execution, the library validates input parameters against the skill's JSON Schema, checking for required fields, type correctness, and allowed enum values.

### Smart Matching Logic
RXON formalizes the rules for matching tasks to holons:
1.  **Hardware Matching**: Compares `HardwareDevice` properties. If a task requires `vram_gb: 16`, it will match any device with `vram_gb >= 16`.
2.  **Resource Properties**: Generic resources (like RAM or CPU cores) are matched via the `properties` dictionary using the same GE logic.
3.  **Capability Intersection**: If a task accepts multiple environments (e.g., `["linux", "darwin"]`), a worker with `linux` will be correctly matched.

## 🧪 Quick Start

```python
from rxon import create_transport
from rxon.models import Resources, HardwareDevice

# 1. Create transport (supports http, https, ws, wss)
transport = create_transport("ws://api.hln.local", "worker-01", "secret-token")

# 2. Define worker resources (RAM/CPU cores are now part of properties)
my_res = Resources(
    properties={"ram_gb": 64, "cpu_cores": 16},
    devices=[HardwareDevice(type="gpu", model="RTX 4090", properties={"vram_gb": 24})]
)

# 3. Smart Matching Logic (Requirement: GPU with at least 16GB VRAM)
req = Resources(devices=[HardwareDevice(type="gpu", properties={"vram_gb": 16})])
if my_res.matches(req):
    print("This holon is ready for the task!")
```

## 📜 License

The project is distributed under the Mozilla Public License 2.0 (MPL 2.0).

---
*Mantra: "The RXON is the medium for the Ghost."*
