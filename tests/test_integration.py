# Copyright (c) 2025-2026 Dmitrii Gagarin aka madgagarin
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import asyncio
import socket
from logging import WARNING
from typing import Any, cast
from uuid import uuid4

import pytest
from aiohttp import ClientSession, WSMsgType, web

from rxon import HttpListener, create_transport
from rxon.constants import (
    ENDPOINT_WORKER_REGISTER,
    EVENT_TYPE_PROGRESS,
    IGNORED_REASON_LATE,
    PROTOCOL_VERSION_HEADER,
)
from rxon.exceptions import RxonAuthError, RxonProtocolError
from rxon.models import (
    DeviceUsage,
    Heartbeat,
    ResourcesUsage,
    SkillInfo,
    TaskPayload,
    TaskResult,
    TokenResponse,
    WorkerCommand,
    WorkerEventPayload,
    WorkerRegistration,
)
from rxon.transports.http import HttpTransport
from rxon.utils import to_dict


@pytest.fixture
def unused_tcp_port_factory() -> Any:
    def factory() -> int:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", 0))
            return cast(int, s.getsockname()[1])

    return factory


@pytest.fixture
async def server(unused_tcp_port_factory: Any) -> Any:
    port = unused_tcp_port_factory()
    app = web.Application()
    listener = HttpListener(app)
    state: dict[str, Any] = {"registered": [], "heartbeats": [], "results": [], "tasks_queue": []}

    async def mock_handler(msg_type: str, payload: Any, context: dict[str, Any]) -> Any:
        if msg_type == "register":
            state["registered"].append(payload)
            return {"status": "registered"}
        elif msg_type == "heartbeat":
            state["heartbeats"].append(payload)
            return {"status": "ok"}
        elif msg_type == "poll":
            if state["tasks_queue"]:
                return state["tasks_queue"].pop(0)
            return None
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


@pytest.mark.asyncio
async def test_full_cycle(server: tuple[str, dict[str, Any], HttpListener]) -> None:
    base_url, state, _ = server
    worker_id = "worker-test-01"
    transport = create_transport(base_url, worker_id, "token")
    await transport.connect()

    try:
        reg = WorkerRegistration(worker_id=worker_id, supported_skills=[])
        await transport.register(reg)
        assert len(state["registered"]) == 1

        usage = ResourcesUsage(10.0, 1.0, [DeviceUsage("gpu-0", 45.0, {"temp": 65})])
        hb = Heartbeat(worker_id, "idle", usage)
        await transport.send_heartbeat(hb)
        assert len(state["heartbeats"]) == 1

        mock_task = TaskPayload("job-1", "task-1", "echo", {"msg": "hi"})
        state["tasks_queue"].append(mock_task)
        task = await transport.poll_task(timeout=1.0)
        assert task is not None
        assert task.job_id == "job-1"

        res = TaskResult("job-1", "task-1", worker_id, "success", data={"reply": "ok"})
        success = await transport.send_result(res)
        assert success is True
        assert len(state["results"]) == 1
    finally:
        await transport.close()


@pytest.mark.asyncio
async def test_heartbeat_hot_skills(server: tuple[str, dict[str, Any], HttpListener]) -> None:
    base_url, state, _ = server
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
    finally:
        await transport.close()


@pytest.mark.asyncio
async def test_auth_refresh_success(server: tuple[str, dict[str, Any], HttpListener]) -> None:
    base_url, _, listener = server

    async def auth_fail_handler(msg_type: str, payload: Any, context: dict[str, Any]) -> Any:
        if msg_type == "heartbeat":
            token = context.get("token")
            if token == "expired-token":
                return web.Response(status=401, text="Token expired")
            return {"status": "ok"}
        if msg_type == "sts_token":
            return {"access_token": "valid-token", "expires_in": 300, "worker_id": "test"}
        return {"status": "ok"}

    listener.handler = auth_fail_handler
    transport = create_transport(base_url, "worker-auth", "expired-token")
    await transport.connect()

    try:
        hb = Heartbeat("worker-auth", "idle", ResourcesUsage(0.0, 0.5, []), [], [], [], None)
        success = await transport.send_heartbeat(hb)
        assert success is not None
        assert cast(HttpTransport, transport).token == "valid-token"
    finally:
        await transport.close()


@pytest.mark.asyncio
async def test_websocket_flow(server: tuple[str, dict[str, Any], HttpListener]) -> None:
    base_url, state, listener = server
    worker_id = "ws-worker"
    progress_received = asyncio.Event()

    async def ws_handler(msg_type: str, payload: Any, context: dict[str, Any]) -> Any:
        if msg_type == "websocket":
            ws = payload
            cmd = WorkerCommand(command="stop_task", task_id="task-99")
            await ws.send_json(to_dict(cmd))

            async for msg in ws:
                if msg.type == WSMsgType.TEXT:
                    data = msg.json()
                    if data.get("event_type") == "progress":
                        state["results"].append(data)
                        progress_received.set()
                        await ws.close()

    listener.handler = ws_handler
    transport = create_transport(base_url, worker_id, "token")
    await transport.connect()

    try:
        command_iterator = transport.listen_for_commands()
        command = await anext(command_iterator)
        assert command.command == "stop_task"

        prog_event = WorkerEventPayload(
            event_id=str(uuid4()),
            worker_id=worker_id,
            origin_worker_id=worker_id,
            event_type=EVENT_TYPE_PROGRESS,
            payload={"progress": 0.5},
        )
        await transport.emit_event(prog_event)
        await asyncio.wait_for(progress_received.wait(), timeout=2.0)
        assert len(state["results"]) == 1
    finally:
        await transport.close()


@pytest.mark.asyncio
async def test_result_ignored(server: tuple[str, dict[str, Any], HttpListener]) -> None:
    base_url, _, listener = server

    async def ignore_handler(msg_type: str, payload: Any, context: dict[str, Any]) -> Any:
        if msg_type == "result":
            return {"status": "ignored", "reason": IGNORED_REASON_LATE}
        return {"status": "ok"}

    listener.handler = ignore_handler
    transport = create_transport(base_url, "worker-ignored", "token")
    await transport.connect()
    try:
        res = TaskResult("job-1", "task-1", "worker-ignored", "success")
        assert await transport.send_result(res) is False
    finally:
        await transport.close()


@pytest.mark.asyncio
async def test_protocol_version_mismatch(unused_tcp_port_factory: Any, caplog: pytest.LogCaptureFixture) -> None:
    port = unused_tcp_port_factory()

    async def handler(request: web.Request) -> web.Response:
        return web.json_response({"status": "ok"}, headers={PROTOCOL_VERSION_HEADER: "99.9.9"})

    app = web.Application()
    app.router.add_post(ENDPOINT_WORKER_REGISTER, handler)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", port)
    await site.start()

    transport = create_transport(f"http://127.0.0.1:{port}", "worker-v", "token")
    await transport.connect()
    try:
        with caplog.at_level(WARNING):
            await transport.register(WorkerRegistration("worker-v"))
            assert "RXON Protocol Version Mismatch" in caplog.text
    finally:
        await transport.close()
        await runner.cleanup()


@pytest.mark.asyncio
async def test_server_garbage_response(unused_tcp_port_factory: Any) -> None:
    port = unused_tcp_port_factory()

    async def handler(request: web.Request) -> web.Response:
        return web.Response(text="<html>Garbage</html>", status=200, content_type="text/html")

    app = web.Application()
    app.router.add_post(ENDPOINT_WORKER_REGISTER, handler)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", port)
    await site.start()

    transport = create_transport(f"http://127.0.0.1:{port}", "worker-g", "token")
    await transport.connect()
    try:
        with pytest.raises(RxonProtocolError, match="not a valid JSON"):
            await transport.register(WorkerRegistration("worker-g"))
    finally:
        await transport.close()
        await runner.cleanup()


@pytest.mark.asyncio
async def test_auth_refresh_failure(server: tuple[str, dict[str, Any], HttpListener]) -> None:
    base_url, _, listener = server

    async def auth_fail_permanent_handler(msg_type: str, payload: Any, context: dict[str, Any]) -> Any:
        if msg_type == "sts_token":
            return web.Response(status=403)
        if context.get("token") == "expired":
            return web.Response(status=401)
        return {"status": "ok"}

    listener.handler = auth_fail_permanent_handler
    transport = create_transport(base_url, "worker-fail", "expired")
    await transport.connect()
    try:
        with pytest.raises(RxonAuthError):
            await transport.send_heartbeat(Heartbeat("worker-fail", "idle"))
    finally:
        await transport.close()


@pytest.mark.asyncio
async def test_network_timeout(server: tuple[str, dict[str, Any], HttpListener]) -> None:
    base_url, _, listener = server

    async def slow_handler(msg_type: str, payload: Any, context: dict[str, Any]) -> Any:
        await asyncio.sleep(2.0)
        return {"status": "ok"}

    listener.handler = slow_handler
    transport = create_transport(base_url, "worker-timeout", "token")
    await transport.connect()
    try:
        # poll_task uses its own timeout, but we test a quick heartbeat
        with pytest.raises(Exception):  # Should be RxonNetworkError/TimeoutError
            await asyncio.wait_for(transport.send_heartbeat(Heartbeat("worker-timeout", "idle")), timeout=0.1)
    finally:
        await transport.close()


@pytest.mark.asyncio
async def test_poll_returns_empty_dict(server: tuple[str, dict[str, Any], HttpListener]) -> None:
    base_url, _, listener = server

    async def empty_poll_handler(msg_type: str, payload: Any, context: dict[str, Any]) -> Any:
        if msg_type == "poll":
            return {}
        return {"status": "ok"}

    listener.handler = empty_poll_handler
    transport = create_transport(base_url, "worker-empty", "token")
    await transport.connect()
    try:
        task = await transport.poll_task(timeout=1.0)
        assert task is None
    finally:
        await transport.close()


@pytest.mark.asyncio
async def test_websocket_error_handling(server: tuple[str, dict[str, Any], HttpListener]) -> None:
    base_url, _, listener = server

    async def bad_ws_handler(msg_type: str, payload: Any, context: dict[str, Any]) -> Any:
        if msg_type == "websocket":
            ws = payload
            await ws.send_str("not-a-json-command")
            await ws.close()

    listener.handler = bad_ws_handler
    transport = create_transport(base_url, "worker-ws", "token")
    await transport.connect()

    try:
        async for _ in transport.listen_for_commands():
            pass
    finally:
        await transport.close()


@pytest.mark.asyncio
async def test_websocket_auth_rejection(server: tuple[str, dict[str, Any], HttpListener]) -> None:
    base_url, _, listener = server

    async def rejection_handler(msg_type: str, payload: Any, context: dict[str, Any]) -> Any:
        if msg_type == "websocket_auth":
            raise PermissionError("Access denied before handshake")
        return {"status": "ok"}

    listener.handler = rejection_handler

    async with ClientSession() as session:
        from rxon.constants import WS_ENDPOINT

        ws_url = f"{base_url.replace('http', 'ws', 1)}{WS_ENDPOINT}/worker-denied"
        try:
            async with session.ws_connect(ws_url) as _:
                pytest.fail("Handshake should not have happened")
        except Exception as e:
            assert "403" in str(e)


@pytest.mark.asyncio
async def test_server_error_500(server: tuple[str, dict[str, Any], HttpListener]) -> None:
    base_url, _, listener = server

    async def server_fail_handler(msg_type: str, payload: Any, context: dict[str, Any]) -> Any:
        return web.Response(status=500, text="Internal Server Error (Simulated)")

    listener.handler = server_fail_handler
    transport = create_transport(base_url, "worker-error", "token")
    await transport.connect()

    try:
        with pytest.raises(RxonProtocolError, match="HTTP 500"):
            await transport.register(WorkerRegistration("worker-error"))
    finally:
        await transport.close()


@pytest.mark.asyncio
async def test_server_error_400_invalid_payload(server: tuple[str, dict[str, Any], HttpListener]) -> None:
    base_url, _, listener = server

    async def bad_request_handler(msg_type: str, payload: Any, context: dict[str, Any]) -> Any:
        return web.Response(status=400, text="Validation error: name is too short")

    listener.handler = bad_request_handler
    transport = create_transport(base_url, "worker-bad", "token")
    await transport.connect()

    try:
        with pytest.raises(RxonProtocolError, match="HTTP 400"):
            await transport.register(WorkerRegistration("worker-bad"))
    finally:
        await transport.close()


@pytest.mark.asyncio
async def test_send_result_mismatch_ignored(server: tuple[str, dict[str, Any], HttpListener]) -> None:
    base_url, _, listener = server

    async def result_mismatch_handler(msg_type: str, payload: Any, context: dict[str, Any]) -> Any:
        if msg_type == "result":
            return {"status": "ignored", "reason": "worker_mismatch"}
        return {"status": "ok"}

    listener.handler = result_mismatch_handler
    transport = create_transport(base_url, "worker-mismatch", "token")
    await transport.connect()
    try:
        res = TaskResult("job-wrong", "task-wrong", "worker-mismatch", "success")
        success = await transport.send_result(res)
        assert success is False
    finally:
        await transport.close()
