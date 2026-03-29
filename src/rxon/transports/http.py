# Copyright (c) 2025-2026 Dmitrii Gagarin aka madgagarin
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

from asyncio import sleep
from collections.abc import AsyncIterator
from logging import getLogger
from ssl import SSLContext
from typing import Any, cast

from aiohttp import (
    ClientError,
    ClientSession,
    ClientTimeout,
    ContentTypeError,
    TCPConnector,
    WSMsgType,
)

from rxon.constants import (
    AUTH_HEADER_WORKER,
    ENDPOINT_TASK_NEXT,
    ENDPOINT_TASK_RESULT,
    ENDPOINT_WORKER_EVENTS,
    ENDPOINT_WORKER_HEARTBEAT,
    ENDPOINT_WORKER_REGISTER,
    IGNORED_REASON_CANCELLED,
    IGNORED_REASON_LATE,
    PROTOCOL_VERSION,
    PROTOCOL_VERSION_HEADER,
    STS_TOKEN_ENDPOINT,
    WS_ENDPOINT,
)
from rxon.exceptions import RxonAuthError, RxonError, RxonNetworkError, RxonProtocolError
from rxon.models import (
    Heartbeat,
    TaskPayload,
    TaskResult,
    TokenResponse,
    WorkerCommand,
    WorkerEventPayload,
    WorkerRegistration,
)
from rxon.utils import from_dict, json_dumps, loads, to_dict

from .base import Transport

logger = getLogger(__name__)


class HttpTransport(Transport):
    """HTTP implementation of RXON Transport using aiohttp."""

    def __init__(
        self,
        base_url: str,
        worker_id: str,
        token: str,
        ssl_context: SSLContext | None = None,
        session: ClientSession | None = None,
        verify_ssl: bool = True,
        result_retries: int = 3,
        result_retry_delay: float = 0.1,
        **kwargs: Any,
    ):
        self.base_url = base_url.rstrip("/")
        self.worker_id = worker_id
        self.token = token
        self.ssl_context = ssl_context
        self._session = session
        self._own_session = False
        self._headers = {
            AUTH_HEADER_WORKER: self.token,
            PROTOCOL_VERSION_HEADER: PROTOCOL_VERSION,
        }
        self.verify_ssl = verify_ssl
        self.result_retries = result_retries
        self.result_retry_delay = result_retry_delay
        self._ws_connection = None
        self._version_warning_logged = False
        self.extra_config = kwargs

    async def connect(self) -> None:
        if not self._session:
            connector = TCPConnector(ssl=self.ssl_context) if self.ssl_context else None
            self._session = ClientSession(connector=connector, json_serialize=json_dumps)
            self._own_session = True

    async def close(self) -> None:
        if self._ws_connection and not self._ws_connection.closed:
            await self._ws_connection.close()
        if self._own_session and self._session and not self._session.closed:
            await self._session.close()

    async def _request(
        self,
        method: str,
        endpoint: str,
        *,
        params: dict[str, Any] | None = None,
        json: Any | None = None,
        timeout: ClientTimeout | None = None,
    ) -> Any:
        if not self._session:
            raise RxonNetworkError("Transport not connected. Call connect() first.")

        url = f"{self.base_url}{endpoint}"
        headers = self._headers.copy()
        for attempt in range(2):
            try:
                async with self._session.request(
                    method, url, params=params, json=json, headers=headers, timeout=timeout
                ) as resp:
                    v = resp.headers.get(PROTOCOL_VERSION_HEADER)
                    if v and v != PROTOCOL_VERSION and not self._version_warning_logged:
                        logger.warning(f"RXON Protocol Version Mismatch! Orchestrator: {v}, Worker: {PROTOCOL_VERSION}")
                        self._version_warning_logged = True

                    if resp.status == 204:
                        return None

                    if resp.status == 401:
                        if attempt == 0 and await self.refresh_token():
                            headers = self._headers.copy()
                            continue
                        raise RxonAuthError(f"Unauthorized (401) from {endpoint}")

                    if resp.status >= 400:
                        text = await resp.text()
                        raise RxonProtocolError(f"HTTP {resp.status}: {text}", details={"status": resp.status})

                    return await resp.json(loads=loads)

            except ContentTypeError as e:
                raise RxonProtocolError(f"Response is not a valid JSON: {e}") from e
            except (ClientError, TimeoutError) as e:
                raise RxonNetworkError(f"Network error during {method} {endpoint}: {e}") from e
            except RxonError:
                raise
            except Exception as e:
                logger.exception("Unexpected error in transport")
                raise RxonError(f"Unexpected transport error: {e}") from e
        return None

    async def refresh_token(self) -> TokenResponse | None:
        if not self._session:
            return None
        url = f"{self.base_url}{STS_TOKEN_ENDPOINT}"
        try:
            async with self._session.post(url, headers=self._headers) as resp:
                if resp.status == 200:
                    data = await resp.json(loads=loads)
                    res = from_dict(TokenResponse, data)
                    self.token = res.access_token
                    self._headers[AUTH_HEADER_WORKER] = self.token
                    logger.info(f"Token refreshed. Expires in {res.expires_in}s")
                    return res
        except Exception as e:
            logger.error(f"Error refreshing token: {e}")
        return None

    async def register(self, registration: WorkerRegistration) -> Any:
        return await self._request("POST", ENDPOINT_WORKER_REGISTER, json=registration)

    async def poll_task(self, timeout: float = 30.0) -> TaskPayload | None:
        endpoint = ENDPOINT_TASK_NEXT.format(worker_id=self.worker_id)
        data = await self._request("GET", endpoint, timeout=ClientTimeout(total=timeout + 5))
        return from_dict(TaskPayload, data) if data else None

    async def send_result(self, result: TaskResult, max_retries: int | None = None, delay: float | None = None) -> bool:
        retries = max_retries if max_retries is not None else self.result_retries
        wait = delay if delay is not None else self.result_retry_delay
        last_error = None
        for i in range(retries):
            try:
                resp = await self._request("POST", ENDPOINT_TASK_RESULT, json=result)
                if isinstance(resp, dict) and resp.get("status") == "ignored":
                    reason = resp.get("reason")
                    msg = f"Result ignored. Reason: {reason}. Job: {result.job_id}"
                    if reason in (IGNORED_REASON_LATE, IGNORED_REASON_CANCELLED):
                        logger.info(msg)
                    else:
                        logger.warning(msg)
                    return False
                return True
            except RxonNetworkError as e:
                last_error = e
            if i < retries - 1:
                await sleep(wait * (2**i))
        if last_error:
            raise last_error
        return False

    async def send_heartbeat(self, heartbeat: Heartbeat) -> dict[str, Any] | None:
        endpoint = ENDPOINT_WORKER_HEARTBEAT.format(worker_id=self.worker_id)
        try:
            return await self._request("PATCH", endpoint, json=heartbeat)
        except RxonError as e:
            logger.warning(f"Heartbeat failed: {e}")
            raise e

    async def emit_event(self, event: WorkerEventPayload) -> bool:
        if self._ws_connection and not self._ws_connection.closed:
            try:
                await self._ws_connection.send_json(to_dict(event))
                return True
            except Exception:
                pass
        try:
            await self._request("POST", ENDPOINT_WORKER_EVENTS, json=event)
            return True
        except RxonError:
            return False

    async def listen_for_commands(self) -> AsyncIterator[WorkerCommand]:
        if not self._session:
            return
        ws_url = f"{self.base_url.replace('http', 'ws', 1)}{WS_ENDPOINT}/{self.worker_id}"
        try:
            async with self._session.ws_connect(ws_url, headers=self._headers) as ws:
                self._ws_connection = cast(Any, ws)
                async for msg in ws:
                    if msg.type == WSMsgType.TEXT:
                        try:
                            data = msg.json(loads=loads)
                            yield from_dict(WorkerCommand, data)
                        except Exception as e:
                            logger.error(f"Failed to parse WebSocket command: {e}")
                    elif msg.type == WSMsgType.ERROR:
                        break
        except Exception as e:
            if not isinstance(e, RxonError):
                logger.error(f"WebSocket connection error: {e}")
                raise RxonError(f"WebSocket connection error: {e}") from e
            raise
        finally:
            self._ws_connection = None
