# Copyright (c) 2025-2026 Dmitrii Gagarin aka madgagarin
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

from typing import List, NamedTuple

from rxon.models import (
    HardwareDevice,
    InstalledArtifact,
    Resources,
    TaskPayload,
    WorkerCapabilities,
    WorkerRegistration,
)
from rxon.utils import to_dict


def test_to_dict_simple():
    class Simple(NamedTuple):
        a: int
        b: str

    obj = Simple(1, "test")
    assert to_dict(obj) == {"a": 1, "b": "test"}


def test_to_dict_nested():
    class Child(NamedTuple):
        val: int

    class Parent(NamedTuple):
        name: str
        child: Child
        children: List[Child]

    obj = Parent("dad", Child(1), [Child(2), Child(3)])
    expected = {"name": "dad", "child": {"val": 1}, "children": [{"val": 2}, {"val": 3}]}
    assert to_dict(obj) == expected


def test_worker_registration_serialization():
    # Construct a complex registration object matching 1.0b5 spec
    reg = WorkerRegistration(
        worker_id="worker-01",
        worker_type="gpu",
        supported_skills=[],
        resources=Resources(
            max_concurrent_tasks=2,
            cpu_cores=8,
            ram_gb=64.0,
            devices=[
                HardwareDevice(
                    type="gpu", model="RTX 4090", id="gpu-0", properties={"vram_gb": 24, "cuda_cores": 16384}
                )
            ],
        ),
        installed_software={"python": "3.11", "cuda": "12.1"},
        installed_artifacts=[
            InstalledArtifact(name="sdxl", version="1.0", type="model", properties={"architecture": "diffusion"})
        ],
        capabilities=WorkerCapabilities(
            hostname="node-1", ip_address="192.168.1.5", cost_per_skill={"gen_image": 0.01}
        ),
    )

    data = to_dict(reg)
    assert data["worker_id"] == "worker-01"
    assert data["resources"]["devices"][0]["model"] == "RTX 4090"
    assert data["resources"]["devices"][0]["properties"]["vram_gb"] == 24
    assert data["installed_artifacts"][0]["properties"]["architecture"] == "diffusion"
    assert data["capabilities"]["cost_per_skill"]["gen_image"] == 0.01


def test_model_field_verification():
    """Ensure TaskPayload has expected fields matching protocol."""
    fields = TaskPayload._fields
    assert "job_id" in fields
    assert "task_id" in fields
    assert "params" in fields
    assert "tracing_context" in fields
    assert "priority" in fields
    assert "deadline" in fields
