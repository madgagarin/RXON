# Copyright (c) 2025-2026 Dmitrii Gagarin aka madgagarin
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import asyncio
import socket
import time
from uuid import uuid4

import pytest
from aiohttp import WSMsgType, web

from rxon import HttpListener, create_transport
from rxon.constants import EVENT_TYPE_PROGRESS, PROTOCOL_VERSION
from rxon.models import (
    DeviceUsage,
    Heartbeat,
    Resources,
    ResourcesUsage,
    SkillInfo,
    TaskPayload,
    TaskResult,
    TokenResponse,
    WorkerCapabilities,
    WorkerCommand,
    WorkerEventPayload,
    WorkerRegistration,
)
from rxon.utils import to_dict

# --- Fixtures ---


@pytest.fixture
def unused_tcp_port_factory():
    """Factory to find an unused port."""

    def factory():
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", 0))
            return s.getsockname()[1]

    return factory


@pytest.fixture
async def server(unused_tcp_port_factory):
    """
    Starts a real aiohttp server with HttpListener.
    Returns the base_url and the listener instance.
    """
    port = unused_tcp_port_factory()
    app = web.Application()
    listener = HttpListener(app)

    # Simple In-Memory Orchestrator Logic
    state = {"registered": [], "heartbeats": [], "results": [], "tasks_queue": []}

    async def mock_handler(msg_type, payload, context):
        if msg_type == "register":
            state["registered"].append(payload)
            return {"status": "registered"}
        elif msg_type == "heartbeat":
            state["heartbeats"].append(payload)
            return {"status": "ok"}
        elif msg_type == "poll":
            # Return a task if available
            if state["tasks_queue"]:
                return state["tasks_queue"].pop(0)
            return None  # 204 No Content
        elif msg_type == "result":
            state["results"].append(payload)
            return {"status": "ok"}
        elif msg_type == "sts_token":
            return TokenResponse(access_token="new_refreshed_token", expires_in=3600, worker_id="test")

    await listener.start(handler=mock_handler)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", port)
    await site.start()

    base_url = f"http://127.0.0.1:{port}"

    yield base_url, state, listener

    await runner.cleanup()


# --- Tests ---


@pytest.mark.asyncio
async def test_full_cycle(server):
    base_url, state, listener = server
    worker_id = "worker-test-01"
    token = "initial-token"

    # 1. Create Transport
    transport = create_transport(base_url, worker_id, token)
    await transport.connect()

    try:
        # 2. Register
        reg = WorkerRegistration(
            worker_id=worker_id,
            worker_type="cpu",
            supported_skills=[],
            resources=Resources(1, 4),
            installed_software={},
            installed_artifacts=[],
            capabilities=WorkerCapabilities("host", "127.0.0.1", {}),
        )

        original_handler = listener.handler

        async def check_version_handler(msg_type, payload, context):
            assert context["protocol_version"] == PROTOCOL_VERSION
            return await original_handler(msg_type, payload, context)

        listener.handler = check_version_handler

        success = await transport.register(reg)
        assert success is not None
        assert len(state["registered"]) == 1
        assert state["registered"][0]["worker_id"] == worker_id
        listener.handler = original_handler

        # 3. Heartbeat with 1.0b5 universal telemetry
        usage = ResourcesUsage(
            cpu_load_percent=10.0,
            ram_used_gb=1.0,
            devices_usage=[DeviceUsage(unit_id="gpu-0", load_percent=45.0, metrics={"temp": 65, "vram_used": 4.2})],
        )
        hb = Heartbeat(worker_id, "idle", usage, [], [], [], None)
        success = await transport.send_heartbeat(hb)
        assert success is not None
        assert len(state["heartbeats"]) == 1
        assert state["heartbeats"][0]["usage"]["devices_usage"][0]["metrics"]["temp"] == 65

        # 4. Poll (Empty)
        task = await transport.poll_task(timeout=1.0)
        assert task is None

        # 5. Poll (With Task)
        # Inject task into server state
        mock_task = TaskPayload(
            job_id="job-1",
            task_id="task-1",
            type="echo",
            params={"msg": "hello"},
            tracing_context={},
            priority=5.0,
        )
        state["tasks_queue"].append(mock_task)

        task = await transport.poll_task(timeout=1.0)
        assert task is not None
        assert task.job_id == "job-1"
        assert task.priority == 5.0
        assert task.params["msg"] == "hello"

        # 6. Send Result
        res = TaskResult("job-1", "task-1", worker_id, "success", data={"reply": "hello world"})
        success = await transport.send_result(res)
        assert success is True
        assert len(state["results"]) == 1
        assert state["results"][0]["data"]["reply"] == "hello world"

    finally:
        await transport.close()


@pytest.mark.asyncio
async def test_heartbeat_hot_skills(server):
    """Test 1.0b5 feature: sending full SkillInfo in hot_skills heartbeat."""
    base_url, state, listener = server
    worker_id = "worker-skills"
    transport = create_transport(base_url, worker_id, "token")
    await transport.connect()

    try:
        skill = SkillInfo(name="echo", description="Returns input")
        usage = ResourcesUsage(0.0, 0.5, [])
        hb = Heartbeat(worker_id=worker_id, status="idle", usage=usage, current_tasks=[], hot_skills=[skill])

        await transport.send_heartbeat(hb)

        assert len(state["heartbeats"]) == 1
        hot_skills = state["heartbeats"][0]["hot_skills"]
        assert len(hot_skills) == 1
        assert hot_skills[0]["name"] == "echo"
        assert hot_skills[0]["description"] == "Returns input"
    finally:
        await transport.close()


@pytest.mark.asyncio
async def test_auth_refresh(server):
    """Test that transport handles 401 by refreshing token and retrying."""
    base_url, state, listener = server

    async def auth_fail_handler(msg_type, payload, context):
        if msg_type == "heartbeat":
            token = context.get("token")
            if token == "expired-token":
                raise web.HTTPUnauthorized(text="Token expired")
            return {"status": "ok"}

        if msg_type == "sts_token":
            return {"access_token": "valid-token", "expires_in": 300, "worker_id": "test"}

        return {"status": "ok"}

    listener.handler = auth_fail_handler

    transport = create_transport(base_url, "worker-auth", "expired-token")
    await transport.connect()

    try:
        hb = Heartbeat("worker-auth", "idle", ResourcesUsage(0.0, 0.5, []), [], [], [], None)

        # This call should:
        # 1. Send heartbeat (fail 401)
        # 2. Call refresh_token (success)
        # 3. Retry heartbeat (success with new token)
        success = await transport.send_heartbeat(hb)

        assert success is not None
        assert transport.token == "valid-token"
    finally:
        await transport.close()


@pytest.mark.asyncio
async def test_websocket_flow(server):
    """Test WebSocket connection: receiving commands and sending progress."""
    base_url, state, listener = server
    worker_id = "ws-worker"

    # Event to signal that server received progress
    progress_received = asyncio.Event()

    async def ws_handler(msg_type, payload, context):
        if msg_type == "websocket":
            ws = payload
            # 1. Send a command to the worker
            cmd = WorkerCommand(command="stop_task", task_id="task-99")
            await ws.send_json(to_dict(cmd))

            # 2. Listen for progress updates from worker
            async for msg in ws:
                if msg.type == WSMsgType.TEXT:
                    data = msg.json()
                    if data.get("event_type") == "progress":
                        state["results"].append(data)  # Store in results for verification
                        progress_received.set()
                        # Close connection after receiving progress to finish the test
                        await ws.close()
                elif msg.type == WSMsgType.ERROR:
                    print("ws connection closed with exception %s", ws.exception())

    listener.handler = ws_handler

    transport = create_transport(base_url, worker_id, "token")
    await transport.connect()

    try:
        # Start listening for commands
        # Since listen_for_commands is an async iterator, we iterate over it.
        # It will yield the command sent by server.

        command_iterator = transport.listen_for_commands()

        # We expect the server to send the command immediately upon connection
        command = await anext(command_iterator)

        assert command.command == "stop_task"
        assert command.task_id == "task-99"

        # Now send progress back to server via emit_event
        prog_event = WorkerEventPayload(
            event_id=str(uuid4()),
            worker_id=worker_id,
            origin_worker_id=worker_id,
            event_type=EVENT_TYPE_PROGRESS,
            payload={"progress": 0.5, "message": "Halfway"},
            bubbling_chain=[],
            target_task_id="task-99",
            target_job_id="job-1",
            timestamp=time.time(),
        )
        sent = await transport.emit_event(prog_event)
        assert sent is True

        # Wait for server to receive it
        await asyncio.wait_for(progress_received.wait(), timeout=2.0)

        # Verify server state
        assert len(state["results"]) == 1
        assert state["results"][0]["payload"]["progress"] == 0.5

    finally:
        await transport.close()
