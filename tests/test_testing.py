# Copyright (c) 2025-2026 Dmitrii Gagarin aka madgagarin
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import pytest

from rxon.models import (
    DeviceUsage,
    Heartbeat,
    Resources,
    ResourcesUsage,
    TaskPayload,
    TaskResult,
    WorkerCapabilities,
    WorkerRegistration,
)
from rxon.testing import MockTransport


@pytest.mark.asyncio
async def test_mock_transport_flow():
    transport = MockTransport(worker_id="mock-1")
    await transport.connect()

    # 1. Register
    reg = WorkerRegistration(
        worker_id="mock-1",
        worker_type="cpu",
        supported_skills=[],
        resources=Resources(1, 1),
        installed_software={},
        installed_artifacts=[],
        capabilities=WorkerCapabilities("h", "i", {}),
    )
    success = await transport.register(reg)
    assert success is not None
    assert success.get("status") == "registered"
    assert len(transport.registered) == 1
    assert transport.registered[0].worker_id == "mock-1"

    # 2. Heartbeat (1.0b5 universal telemetry)
    usage = ResourcesUsage(
        cpu_load_percent=5.0,
        ram_used_gb=0.5,
        devices_usage=[DeviceUsage(unit_id="sensor-1", load_percent=0.0, metrics={"battery": 85})],
    )
    hb = Heartbeat("mock-1", "idle", usage, [])
    await transport.send_heartbeat(hb)
    assert len(transport.heartbeats) == 1
    assert transport.heartbeats[0].usage.devices_usage[0].metrics["battery"] == 85

    # 3. Poll (Empty)
    task = await transport.poll_task(timeout=0.1)
    assert task is None

    # 4. Poll (With Task)
    mock_task = TaskPayload(
        job_id="job1", task_id="task1", type="echo", params={"msg": "hi"}, tracing_context={}, priority=10.0
    )
    transport.push_task(mock_task)

    task = await transport.poll_task(timeout=1.0)
    assert task is not None
    assert task.job_id == "job1"
    assert task.priority == 10.0

    # 5. Result
    res = TaskResult(job_id="job1", task_id="task1", worker_id="mock-1", status="success", data={"ok": True})
    success = await transport.send_result(res)
    assert success is True
    assert len(transport.results) == 1
    assert transport.results[0].data["ok"] is True

    await transport.close()
