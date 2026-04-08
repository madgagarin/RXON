# Copyright (c) 2025-2026 Dmitrii Gagarin aka madgagarin
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.


from rxon.models import (
    HardwareDevice,
    Heartbeat,
    Resources,
    SecurityContext,
    TaskPayload,
    TaskResult,
    WorkerRegistration,
)
from rxon.utils import to_dict


def test_worker_registration_serialization() -> None:
    reg = WorkerRegistration(
        worker_id="test-1",
        supported_skills=[],
        resources=Resources(cpu_cores=4, ram_gb=16.0),
        security=SecurityContext(signature="sig123", signer_id="boss"),
    )
    d = to_dict(reg)
    assert d["worker_id"] == "test-1"
    assert d["resources"]["cpu_cores"] == 4
    assert d["security"]["signature"] == "sig123"


def test_task_payload_defaults() -> None:
    task = TaskPayload(job_id="j1", task_id="t1", type="echo")
    assert task.priority == 0.0
    assert task.params is None
    assert task.deadline is None


def test_hardware_device_to_dict() -> None:
    dev = HardwareDevice(type="gpu", model="A100", properties={"vram": 40})
    d = to_dict(dev)
    assert d["type"] == "gpu"
    assert d["properties"]["vram"] == 40


def test_resources_default_concurrent() -> None:
    res = Resources()
    assert res.max_concurrent_tasks == 1


def test_security_context_empty() -> None:
    sc = SecurityContext()
    assert sc.signature is None
    assert sc.signer_id is None


def test_task_result_minimal() -> None:
    res = TaskResult(job_id="j1", task_id="t1", worker_id="w1", status="success")
    assert res.status == "success"
    assert res.data is None


def test_models_empty_collections_serialization() -> None:
    hb = Heartbeat(
        worker_id="w1",
        status="idle",
        current_tasks=[],
        metadata={},
    )
    d = to_dict(hb)
    assert d["current_tasks"] == []
    assert d["metadata"] == {}

    hb2 = Heartbeat(worker_id="w2", status="idle")
    d2 = to_dict(hb2)
    assert d2["current_tasks"] is None
    assert d2["metadata"] is None


def test_heartbeat_minimal() -> None:
    hb = Heartbeat(worker_id="w1", status="busy")
    assert hb.worker_id == "w1"
    assert hb.status == "busy"
    assert hb.usage is None
