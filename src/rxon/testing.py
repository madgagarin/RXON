# Copyright (c) 2025-2026 Dmitrii Gagarin aka madgagarin
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

from asyncio import Queue, wait_for
from collections.abc import AsyncIterator
from typing import Any

from rxon.models import (
    Heartbeat,
    TaskPayload,
    TaskResult,
    TokenResponse,
    WorkerCommand,
    WorkerEventPayload,
    WorkerRegistration,
)
from rxon.transports.base import Transport
from rxon.utils import from_dict


class MockTransport(Transport):
    """
    In-memory mock transport for testing Workers without a real Orchestrator.
    Imitates real transport behavior by ensuring returned objects are proper models.
    """

    def __init__(self, worker_id: str = "mock-worker", token: str = "mock-token", **kwargs: Any):
        self.worker_id = worker_id
        self.token = token
        self.connected = False
        self.registered: list[WorkerRegistration] = []
        self.heartbeats: list[Heartbeat] = []
        self.results: list[TaskResult] = []
        self.emitted_events: list[WorkerEventPayload] = []
        self.task_queue: Queue[Any] = Queue()
        self.command_queue: Queue[Any] = Queue()
        self.extra_config = kwargs

    async def connect(self) -> None:
        self.connected = True

    async def close(self) -> None:
        self.connected = False

    async def register(self, registration: WorkerRegistration) -> dict[str, Any]:
        self.registered.append(registration)
        return {"status": "registered", "worker_id": self.worker_id}

    async def poll_task(self, timeout: float = 30.0) -> TaskPayload | None:
        try:
            item = await wait_for(self.task_queue.get(), timeout=timeout)
            if isinstance(item, dict):
                return from_dict(TaskPayload, item)
            return item
        except Exception:
            return None

    async def send_result(self, result: TaskResult) -> bool:
        self.results.append(result)
        return True

    async def send_heartbeat(self, heartbeat: Heartbeat) -> dict[str, Any]:
        self.heartbeats.append(heartbeat)
        return {"status": "ok"}

    async def emit_event(self, event: WorkerEventPayload) -> bool:
        self.emitted_events.append(event)
        return True

    async def listen_for_commands(self) -> AsyncIterator[WorkerCommand]:
        while self.connected:
            item = await self.command_queue.get()
            if isinstance(item, dict):
                yield from_dict(WorkerCommand, item)
            else:
                yield item

    async def refresh_token(self) -> TokenResponse:
        self.token = "refreshed-mock-token"
        return TokenResponse(access_token=self.token, expires_in=3600, worker_id=self.worker_id)

    def push_task(self, task: TaskPayload | dict[str, Any]):
        """Inject a task into the queue for the worker to pick up."""
        self.task_queue.put_nowait(task)

    def push_command(self, command: WorkerCommand | dict[str, Any]):
        """Inject a command into the queue."""
        self.command_queue.put_nowait(command)
