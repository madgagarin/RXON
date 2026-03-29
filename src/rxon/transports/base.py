# Copyright (c) 2025-2026 Dmitrii Gagarin aka madgagarin
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Any  # noqa: TID251

from rxon.models import (
    Heartbeat,
    TaskPayload,
    TaskResult,
    TokenResponse,
    WorkerCommand,
    WorkerEventPayload,
    WorkerRegistration,
)


class Transport(ABC):
    """
    Abstract base class for RXON Worker-side Transports.
    """

    @abstractmethod
    async def connect(self) -> None:
        """Initialize connection/session."""
        pass

    @abstractmethod
    async def close(self) -> None:
        """Close connection and release resources."""
        pass

    @abstractmethod
    async def register(self, registration: WorkerRegistration) -> Any:
        """Register the worker and return server response."""
        pass

    @abstractmethod
    async def poll_task(self, timeout: float = 30.0) -> TaskPayload | None:
        """Wait for the next task from the orchestrator."""
        pass

    @abstractmethod
    async def send_result(self, result: TaskResult) -> bool:
        """Send task execution result to orchestrator."""
        pass

    @abstractmethod
    async def send_heartbeat(self, heartbeat: Heartbeat) -> Any | None:
        """Send health and usage info to orchestrator."""
        pass

    @abstractmethod
    async def emit_event(self, event: WorkerEventPayload) -> bool:
        """Emit a real-time event/telemetry to orchestrator."""
        pass

    @abstractmethod
    def listen_for_commands(self) -> AsyncIterator[WorkerCommand]:
        """Listen for incoming commands from the orchestrator."""
        pass

    @abstractmethod
    async def refresh_token(self) -> TokenResponse | None:
        """Request a new access token using STS."""
        pass


class Listener(ABC):
    """
    Abstract base class for RXON Orchestrator-side Listeners.
    """

    @abstractmethod
    async def start(
        self,
        handler: Callable[[str, Any, dict[str, Any]], Awaitable[Any]],
    ) -> None:
        """
        Start listening for worker connections.
        handler: async function(action, payload, context) -> response
        context contains authentication info (e.g., 'token', 'worker_id').
        """
        pass

    @abstractmethod
    async def stop(self) -> None:
        """
        Stop the listener and release ports/resources.
        """
        pass
