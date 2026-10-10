# RXON (Reverse Axon) Protocol

**EN** | [ES](https://github.com/madgagarin/rxon/blob/main/docs/es/README.md) | [RU](https://github.com/madgagarin/rxon/blob/main/docs/ru/README.md)

[![License: MPL 2.0](https://img.shields.io/badge/License-MPL%202.0-brightgreen.svg)](https://opensource.org/licenses/MPL-2.0)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/release/python-3110/)
[![PyPI version](https://img.shields.io/pypi/v/rxon.svg)](https://pypi.org/project/rxon/)

**RXON** (Reverse Axon) is a lightweight protocol for reverse connections, task distribution, and typed inter-service communication within **[HLN (Holarchical Logic Network)](https://github.com/madgagarin/hln)** systems.

It provides a strictly typed message foundation and Zero Trust payload verification for distributed agent runtimes.

## Concept

In conventional client-server architectures, control planes push requests down to worker nodes. In **RXON**, worker nodes (shells) initiate outbound connections to the orchestrator to pull tasks. This reverse-connection pattern allows workers to operate behind firewalls and NAT without inbound port forwarding, while establishing a bidirectional communication channel.

## Key Features

- **Reverse connection (pull model)**: Worker nodes initiate outbound connections to orchestrators to receive tasks, simplifying deployment behind NAT and firewalls.
- **Zero Trust payload verification**: Message signing with HMAC-SHA256 (symmetric) and Ed25519 (asymmetric), constant-time signature comparison, call-chain tracking (`bubbling_chain`), and task authorization signatures (`sig`).
- **Policy and telemetry tracking**: Built-in support for execution constraints (`policy`), holarchy call depth (`depth`), execution step counters (`step`), event hash linking (`parent_hash`), execution cost reporting (`costs`), risk levels (`risk`), and required permissions (`permissions`).
- **Execution receipts**: `ExecutionReceipt` schema for recording advisory routing decisions, candidate evaluations, fallback triggers, and decision latency.
- **Schema inference and validation**: Generates JSON Schemas from Python handler signatures (`msgspec.Struct`, `dataclass`, models implementing `model_json_schema`, primitives). Caches compiled validators with a thread-safe bounded LRU cache (up to 2048 entries).
- **Deterministic serialization**: `to_dict` normalizes floating-point values (e.g., `1.0` -> `1`), strips `None` values, and sorts keys via `orjson` to ensure reproducible cryptographic hashes.
- **Model conversion**: `from_dict` utility based on `msgspec` to convert dictionaries into typed structures (`Struct`, `dataclass`, `Enum`, `UUID`, `datetime`).
- **Resource matching**: Matches hardware devices and worker resources against task requirements using greater-than-or-equal (numeric) and set intersection/inclusion rules.
- **Transport resilience**: WebSocket and HTTP polling transports with token refresh, exponential backoff, and HTTP 429 (`Retry-After`) handling.

## Ecosystem

RXON is the foundational protocol powering the distributed multi-agent automation stack:

- **[HLN (Holarchical Logic Network)](https://github.com/madgagarin/hln)**: Architecture and specification for self-similar holarchies.
- **[Shellspirit](https://github.com/madgagarin/shellspirit)**: State-machine based orchestrator for long-running AI workflows and distributed execution.
- **[Shellnode](https://github.com/madgagarin/shellnode)**: Python SDK for building workers (holons) that connect to orchestrators via RXON.

## Architecture & Logic

### Data Integrity & Validation

1. **Serialization stability**: RXON uses `orjson` to produce canonical JSON: floating-point whole numbers are normalized (`10.0` -> `10`), dictionary keys are sorted, and non-string keys are converted to strings. This ensures identical cryptographic hashes for equivalent payloads.
2. **Type support**: First-class support for `msgspec.Struct`, standard library `dataclass`, `datetime`, `UUID`, `Enum`, and models exposing `model_json_schema()` or `schema()`.
3. **Recursion depth limit**: Recursive traversal in serialization helpers is bounded to 30 levels to prevent stack exhaustion on deeply nested or cyclic payloads.
4. **Schema enforcement**: JSON Schemas are compiled and cached in memory. Before task execution, parameters can be validated against the skill's input schema to reject missing required fields or type mismatches early.

### Resource Matching

RXON defines declarative matching rules between worker resources and task requirements:

1. **Hardware devices**: Evaluates `HardwareDevice` properties. Numeric requirements use greater-than-or-equal matching (e.g. `vram_gb: 16` requires `vram_gb >= 16`).
2. **Generic properties**: Scalar attributes in `properties` follow the same greater-than-or-equal comparison.
3. **Capability sets**: When requirements specify a collection of acceptable values (e.g. `["linux", "darwin"]`), matching checks for membership or non-empty set intersection.

### Execution Context & Governance

- **Policy constraints (`policy`)**: Dict containing execution constraints (e.g. allowed skills, token limits, budget caps).
- **Call hierarchy (`depth`, `step`, `parent_hash`)**: Tracks call nesting depth (`depth`), workflow step sequence (`step`), and parent event hash (`parent_hash`).
- **Task signature (`sig`)**: HMAC-SHA256 signature generated by the orchestrator using `ORCHESTRATOR_SECRET_KEY` and verified by the worker prior to execution.
- **Timestamp (`timestamp`)**: Integer Unix timestamp in seconds (`int`) to avoid floating-point rounding discrepancies across systems.
- **Cost reporting (`costs`)**: `TaskResult.costs` field for metrics such as consumed tokens, duration, or currency amounts (e.g. `{"tokens": 1500, "usd": 0.02}`).

## Standard Error Codes

- `CONTRACT_VIOLATION_ERROR`: Payload does not conform to the expected schema.
- `SECURITY_ERROR`: Authentication failure, token expiration, or signature mismatch.
- `RESOURCE_EXHAUSTED_ERROR`: Worker has insufficient memory, GPU, or compute capacity.
- `DEPENDENCY_ERROR`: Required upstream service, worker, or artifact is unavailable.

## Quick Start

### Worker Side (Pull)

```python
from rxon import create_transport
from rxon.models import HardwareDevice, Resources

# 1. Initialize transport (supports http, https, ws, wss)
transport = create_transport("ws://api.hln.local", "worker-01", "secret-token")

# 2. Define worker resources
my_res = Resources(
    properties={"ram_gb": 64, "cpu_cores": 16},
    devices=[HardwareDevice(type="gpu", model="RTX 4090", properties={"vram_gb": 24})],
)

# 3. Match against task requirements (e.g., GPU with at least 16GB VRAM)
req = Resources(devices=[HardwareDevice(type="gpu", properties={"vram_gb": 16})])
if my_res.matches(req):
    print("Worker meets requirements")
```

### Orchestrator Side (Server)

```python
from aiohttp import web
from rxon import HttpListener

app = web.Application()
listener = HttpListener(app)

# Register RXON routes before startup
listener.setup_routes()


async def my_handler(action, payload, context):
    if action == "poll":
        return {"job_id": "j-1", "task_id": "t-1", "type": "echo"}
    return {"status": "ok"}


await listener.start(handler=my_handler)
```

## License

This project is licensed under the Mozilla Public License 2.0 (MPL 2.0).

---

_Mantra: "The RXON is the medium for the Ghost."_
