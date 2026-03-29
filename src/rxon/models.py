# Copyright (c) 2025-2026 Dmitrii Gagarin aka madgagarin
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

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
    "SecurityContext",
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
    type: str
    model: str | None = None
    id: str | None = None
    properties: dict[str, Any] | None = None
    metrics: dict[str, Any] | None = None

    def matches(self, req: "HardwareDevice") -> bool:
        """Checks if this device matches the requirements using Smart Comparison (GE logic for numbers)."""
        if req.type and self.type != req.type:
            return False

        if req.model and (not self.model or req.model.lower() not in self.model.lower()):
            return False

        if req.id and self.id != req.id:
            return False

        if not req.properties:
            return True

        my_props = self.properties or {}
        for k, req_v in req.properties.items():
            my_v = my_props.get(k)
            if my_v is None:
                return False

            if isinstance(req_v, (int, float)) and isinstance(my_v, (int, float)):
                if my_v < req_v:
                    return False
            elif my_v != req_v:
                return False
        return True


class DeviceUsage(NamedTuple):
    unit_id: str
    load_percent: float
    metrics: dict[str, Any] | None = None


class ResourcesUsage(NamedTuple):
    cpu_load_percent: float = 0.0
    ram_used_gb: float = 0.0
    devices_usage: list[DeviceUsage] | None = None


class Resources(NamedTuple):
    max_concurrent_tasks: int = 1
    cpu_cores: int | None = None
    ram_gb: float | None = None
    devices: list[HardwareDevice] | None = None
    properties: dict[str, Any] | None = None

    def matches(self, req: "Resources") -> bool:
        """Checks if these resources meet the requirements (GE logic for compute fields)."""
        if req.cpu_cores and (self.cpu_cores or 0) < req.cpu_cores:
            return False
        if req.ram_gb and (self.ram_gb or 0.0) < req.ram_gb:
            return False

        if req.devices:
            my_devices = list(self.devices or [])
            for req_dev in req.devices:
                found_idx = -1
                for i, my_dev in enumerate(my_devices):
                    if my_dev.matches(req_dev):
                        found_idx = i
                        break
                if found_idx == -1:
                    return False
                my_devices.pop(found_idx)

        if req.properties:
            my_props = self.properties or {}
            for k, req_v in req.properties.items():
                my_v = my_props.get(k)
                if my_v is None:
                    return False
                if isinstance(req_v, (int, float)) and isinstance(my_v, (int, float)):
                    if my_v < req_v:
                        return False
                elif my_v != req_v:
                    return False
        return True


class InstalledArtifact(NamedTuple):
    name: str
    version: str = "unknown"
    type: str | None = None
    properties: dict[str, Any] | None = None

    def matches(self, req: "InstalledArtifact") -> bool:
        if self.name != req.name:
            return False
        if req.version != "unknown" and req.version != self.version:
            return False

        if not req.properties:
            return True

        my_props = self.properties or {}
        for k, req_v in req.properties.items():
            my_v = my_props.get(k)
            if my_v is None:
                return False
            if isinstance(req_v, (int, float)) and isinstance(my_v, (int, float)):
                if my_v < req_v:
                    return False
            elif my_v != req_v:
                return False
        return True


@dataclass(frozen=True, slots=True)
class SkillInfo:
    name: str
    type: str | None = None
    description: str | None = None
    version: str | None = None
    input_schema: dict[str, Any] | None = None
    output_schema: dict[str, Any] | None = None
    events_schema: dict[str, dict[str, Any]] | None = None
    output_statuses: list[str] | None = None
    schema_dialect: str = "json-schema"
    properties: dict[str, Any] | None = None

    def __lt__(self, other: Any) -> bool:
        if not isinstance(other, SkillInfo):
            return NotImplemented
        return self.name < other.name


class SecurityContext(NamedTuple):
    """Security metadata for Zero Trust identity and verification."""

    signature: str | None = None
    signer_id: str | None = None
    identity_chain: list[str] | None = None
    metadata: dict[str, Any] | None = None


class WorkerCapabilities(NamedTuple):
    hostname: str = "unknown"
    ip_address: str = "0.0.0.0"
    cost_per_skill: dict[str, float] | None = None
    s3_config_hash: str | None = None
    extra: dict[str, Any] | None = None


class FileMetadata(NamedTuple):
    uri: str
    size: int = 0
    etag: str | None = None
    metadata: dict[str, Any] | None = None


class WorkerRegistration(NamedTuple):
    worker_id: str
    worker_type: str = "generic"
    supported_skills: list[SkillInfo] | None = None
    resources: Resources | None = None
    installed_software: dict[str, str] | None = None
    installed_artifacts: list[InstalledArtifact] | None = None
    capabilities: WorkerCapabilities | None = None
    skills_hash: str | None = None
    security: SecurityContext | None = None
    metadata: dict[str, Any] | None = None


class TokenResponse(NamedTuple):
    access_token: str
    expires_in: int
    worker_id: str
    metadata: dict[str, Any] | None = None


class WorkerEventPayload(NamedTuple):
    event_id: str
    worker_id: str
    origin_worker_id: str
    event_type: str
    payload: dict[str, Any]
    bubbling_chain: list[str] | None = None
    target_job_id: str | None = None
    target_task_id: str | None = None
    trace_context: dict[str, str] | None = None
    priority: float = 0.0
    timestamp: float | None = None
    security: SecurityContext | None = None
    metadata: dict[str, Any] | None = None


class WorkerCommand(NamedTuple):
    command: str
    task_id: str | None = None
    job_id: str | None = None
    params: dict[str, Any] | None = None
    metadata: dict[str, Any] | None = None


class TaskPayload(NamedTuple):
    job_id: str
    task_id: str
    type: str
    params: dict[str, Any] | None = None
    tracing_context: dict[str, str] | None = None
    params_metadata: dict[str, FileMetadata] | None = None
    priority: float = 0.0
    deadline: float | None = None
    security: SecurityContext | None = None
    metadata: dict[str, Any] | None = None


class TaskError(NamedTuple):
    code: str
    message: str
    details: dict[str, Any] | None = None


class TaskResult(NamedTuple):
    job_id: str
    task_id: str
    worker_id: str
    status: str
    data: dict[str, Any] | None = None
    error: TaskError | None = None
    data_metadata: dict[str, FileMetadata] | None = None
    security: SecurityContext | None = None
    metadata: dict[str, Any] | None = None


class Heartbeat(NamedTuple):
    worker_id: str
    status: str
    usage: ResourcesUsage | None = None
    current_tasks: list[str] | None = None
    supported_skills: list[SkillInfo] | None = None
    hot_cache: list[str] | None = None
    skill_dependencies: dict[str, list[str]] | None = None
    hot_skills: list[SkillInfo] | None = None
    skills_hash: str | None = None
    security: SecurityContext | None = None
    metadata: dict[str, Any] | None = None
