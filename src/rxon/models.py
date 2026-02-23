from dataclasses import dataclass
from typing import Any, NamedTuple

__all__ = [
    "HardwareDevice",
    "DeviceUsage",
    "ResourcesUsage",
    "Resources",
    "InstalledArtifact",
    "SkillInfo",
    "WorkerCapabilities",
    "FileMetadata",
    "WorkerRegistration",
    "TokenResponse",
    "WorkerEventPayload",
    "WorkerCommand",
    "TaskPayload",
    "TaskError",
    "TaskResult",
    "Heartbeat",
]


class HardwareDevice(NamedTuple):
    """
    General description of a hardware device (GPU, TPU, NPU, etc.)
    """

    type: str  # gpu, tpu, npu, etc.
    model: str
    memory_gb: int | None = None


class DeviceUsage(NamedTuple):
    """
    Current usage metrics for a specific hardware device.
    """

    unit_id: str  # Index or UUID of the device
    load_percent: float
    memory_used_gb: float | None = None
    temperature: float | None = None


class ResourcesUsage(NamedTuple):
    """
    Detailed resource usage report.
    """

    cpu_load_percent: float
    ram_used_gb: float
    devices_usage: list[DeviceUsage] | None = None


class Resources(NamedTuple):
    max_concurrent_tasks: int
    cpu_cores: int
    ram_gb: float | None = None
    devices: list[HardwareDevice] | None = None


class InstalledArtifact(NamedTuple):
    """
    General description of an installed asset (Model, Binary, Dataset, etc.)
    """

    name: str
    version: str
    type: str | None = None  # model, binary, library, etc.


@dataclass(frozen=True, slots=True)
class SkillInfo:
    """
    Base class for skill definitions in the Hierarchical Logic Network.
    Immutable and extensible via inheritance.
    """

    name: str
    type: str | None = None
    description: str | None = None
    version: str | None = None
    input_schema: dict[str, Any] | None = None
    output_schema: dict[str, Any] | None = None
    events_schema: dict[str, dict[str, Any]] | None = None
    output_statuses: list[str] | None = None

    def __lt__(self, other: Any) -> bool:
        if not isinstance(other, SkillInfo):
            return NotImplemented
        return self.name < other.name


class WorkerCapabilities(NamedTuple):
    hostname: str
    ip_address: str
    cost_per_skill: dict[str, float]
    s3_config_hash: str | None = None
    extra: dict[str, Any] | None = None


class FileMetadata(NamedTuple):
    uri: str
    size: int
    etag: str | None = None


class WorkerRegistration(NamedTuple):
    worker_id: str
    worker_type: str
    supported_skills: list[SkillInfo]
    resources: Resources
    installed_software: dict[str, str]
    installed_artifacts: list[InstalledArtifact]
    capabilities: WorkerCapabilities
    skills_hash: str | None = None


class TokenResponse(NamedTuple):
    access_token: str
    expires_in: int
    worker_id: str


class WorkerEventPayload(NamedTuple):
    event_id: str  # UUID for idempotency
    worker_id: str  # Current sender ID (the one who emits to the transport)
    origin_worker_id: str  # The atomic worker who originally created the event
    event_type: str  # Matches a key in events_schema
    payload: dict[str, Any]
    bubbling_chain: list[str]  # List of holon IDs that bubbled this event
    target_job_id: str | None = None
    target_task_id: str | None = None
    trace_context: dict[str, str] | None = None
    priority: float = 0.0
    timestamp: float | None = None


class WorkerCommand(NamedTuple):
    command: str
    task_id: str | None = None
    job_id: str | None = None
    params: dict[str, Any] | None = None


class TaskPayload(NamedTuple):
    job_id: str
    task_id: str
    type: str
    params: dict[str, Any]
    tracing_context: dict[str, str]
    params_metadata: dict[str, FileMetadata] | None = None
    priority: float = 0.0
    deadline: float | None = None


class TaskError(NamedTuple):
    code: str
    message: str
    details: dict[str, Any] | None = None


class TaskResult(NamedTuple):
    job_id: str
    task_id: str
    worker_id: str
    status: str  # success, failure, cancelled
    data: dict[str, Any] | None = None
    error: TaskError | None = None
    data_metadata: dict[str, FileMetadata] | None = None


class Heartbeat(NamedTuple):
    worker_id: str
    status: str
    usage: ResourcesUsage
    current_tasks: list[str]
    supported_skills: list[SkillInfo] | None = None
    hot_cache: list[str] | None = None
    skill_dependencies: dict[str, list[str]] | None = None
    hot_skills: list[str] | None = None
    skills_hash: str | None = None
