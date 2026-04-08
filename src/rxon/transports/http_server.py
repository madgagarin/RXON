# Copyright (c) 2025-2026 Dmitrii Gagarin aka madgagarin
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

from aiohttp import web

from rxon.constants import (
    AUTH_HEADER_WORKER,
    ENDPOINT_TASK_NEXT,
    ENDPOINT_TASK_RESULT,
    ENDPOINT_WORKER_EVENTS,
    ENDPOINT_WORKER_HEARTBEAT,
    ENDPOINT_WORKER_REGISTER,
    PROTOCOL_VERSION,
    PROTOCOL_VERSION_HEADER,
    STS_TOKEN_ENDPOINT,
    WS_ENDPOINT,
)
from rxon.security import extract_cert_identity
from rxon.utils import json_dumps, loads, to_dict

from .base import Listener

T = TypeVar("T")


class HttpListener(Listener):
    """
    HTTP implementation of RXON Listener using aiohttp.
    """

    def __init__(self, app: web.Application):
        self.app = app
        self.handler: Callable[[str, Any, dict[str, Any]], Awaitable[Any]] | None = None
        self._setup_middleware()

    def _setup_middleware(self) -> None:
        @web.middleware
        async def version_middleware(
            request: web.Request, handler: Callable[[web.Request], Awaitable[web.StreamResponse]]
        ) -> web.StreamResponse:
            response = await handler(request)
            response.headers[PROTOCOL_VERSION_HEADER] = PROTOCOL_VERSION
            return response

        self.app.middlewares.append(version_middleware)

    async def start(
        self,
        handler: Callable[[str, Any, dict[str, Any]], Awaitable[Any]],
    ) -> None:
        self.handler = handler
        self._setup_routes()

    async def stop(self) -> None:
        # App lifecycle is managed externally
        pass

    def _setup_routes(self) -> None:
        self.app.router.add_post(ENDPOINT_WORKER_REGISTER, self._handle_register)
        self.app.router.add_get(ENDPOINT_TASK_NEXT, self._handle_poll)
        self.app.router.add_post(ENDPOINT_TASK_RESULT, self._handle_result)
        self.app.router.add_patch(ENDPOINT_WORKER_HEARTBEAT, self._handle_heartbeat)
        self.app.router.add_post(ENDPOINT_WORKER_EVENTS, self._handle_event)
        self.app.router.add_post(STS_TOKEN_ENDPOINT, self._handle_sts)

        # WebSocket endpoint
        self.app.router.add_get(f"{WS_ENDPOINT}/{{worker_id}}", self._handle_ws)

    @staticmethod
    def _extract_context(request: web.Request) -> dict[str, Any]:
        token = request.headers.get(AUTH_HEADER_WORKER)
        version = request.headers.get(PROTOCOL_VERSION_HEADER)
        cert_id = extract_cert_identity(request)

        return {
            "token": token,
            "protocol_version": version,
            "cert_identity": cert_id,
            "transport": "http",
            "raw_request": request,
        }

    def _json_response(self, data: Any, **kwargs: Any) -> web.Response:
        if isinstance(data, web.Response):
            return data
        return web.json_response(to_dict(data), dumps=json_dumps, **kwargs)

    async def _handle_register(self, request: web.Request) -> web.Response:
        try:
            data = await request.json(loads=loads)
            payload = data

            context = self._extract_context(request)
            if self.handler:
                resp = await self.handler("register", payload, context)
                return self._json_response(resp or {"status": "registered"})
            return self._json_response({"error": "No handler configured"}, status=500)
        except web.HTTPException as e:
            return self._json_response({"error": e.text or str(e)}, status=e.status)
        except PermissionError as e:
            return self._json_response({"error": str(e)}, status=403)
        except ValueError as e:
            return self._json_response({"error": str(e)}, status=400)
        except Exception as e:
            return self._json_response({"error": str(e)}, status=500)

    async def _handle_poll(self, request: web.Request) -> web.Response:
        try:
            worker_id = request.match_info.get("worker_id")
            if not worker_id:
                return self._json_response({"error": "worker_id required"}, status=400)

            context = self._extract_context(request)
            context["worker_id_hint"] = worker_id  # Important for auth

            if self.handler:
                task = await self.handler("poll", worker_id, context)
                if task:
                    return self._json_response(task)
                return web.Response(status=204)
            return web.Response(status=500)
        except web.HTTPException as e:
            return self._json_response({"error": e.text or str(e)}, status=e.status)
        except PermissionError as e:
            return self._json_response({"error": str(e)}, status=403)
        except ValueError as e:
            return self._json_response({"error": str(e)}, status=400)
        except Exception as e:
            return self._json_response({"error": str(e)}, status=500)

    async def _handle_result(self, request: web.Request) -> web.Response:
        try:
            data = await request.json(loads=loads)
            payload = data

            context = self._extract_context(request)
            if self.handler:
                resp = await self.handler("result", payload, context)
                return self._json_response(resp or {"status": "ok"})
            return self._json_response({"error": "No handler configured"}, status=500)
        except web.HTTPException as e:
            return self._json_response({"error": e.text or str(e)}, status=e.status)
        except PermissionError as e:
            return self._json_response({"error": str(e)}, status=403)
        except ValueError as e:
            return self._json_response({"error": str(e)}, status=400)
        except Exception as e:
            return self._json_response({"error": str(e)}, status=500)

    async def _handle_heartbeat(self, request: web.Request) -> web.Response:
        try:
            worker_id = request.match_info.get("worker_id")
            data = None
            if request.can_read_body:
                data = await request.json(loads=loads)

            payload = data
            context = self._extract_context(request)
            context["worker_id_hint"] = worker_id

            if self.handler:
                resp = await self.handler("heartbeat", payload, context)
                return self._json_response(resp)
            return web.Response(status=500)
        except web.HTTPException as e:
            return self._json_response({"error": e.text or str(e)}, status=e.status)
        except PermissionError as e:
            return self._json_response({"error": str(e)}, status=403)
        except ValueError as e:
            return self._json_response({"error": str(e)}, status=400)
        except Exception as e:
            return self._json_response({"error": str(e)}, status=500)

    async def _handle_event(self, request: web.Request) -> web.Response:
        try:
            data = await request.json(loads=loads)
            payload = data

            context = self._extract_context(request)
            if self.handler:
                resp = await self.handler("event", payload, context)
                return self._json_response(resp or {"status": "event_accepted"})
            return self._json_response({"error": "No handler configured"}, status=500)
        except web.HTTPException as e:
            return self._json_response({"error": e.text or str(e)}, status=e.status)
        except PermissionError as e:
            return self._json_response({"error": str(e)}, status=403)
        except ValueError as e:
            return self._json_response({"error": str(e)}, status=400)
        except Exception as e:
            return self._json_response({"error": str(e)}, status=500)

    async def _handle_sts(self, request: web.Request) -> web.Response:
        try:
            context = self._extract_context(request)
            if self.handler:
                token_data = await self.handler("sts_token", None, context)
                return self._json_response(token_data)
            return web.Response(status=500)
        except web.HTTPException as e:
            return self._json_response({"error": e.text or str(e)}, status=e.status)
        except PermissionError as e:
            return self._json_response({"error": str(e)}, status=403)
        except ValueError as e:
            return self._json_response({"error": str(e)}, status=400)
        except Exception as e:
            return self._json_response({"error": str(e)}, status=500)

    async def _handle_ws(self, request: web.Request) -> web.StreamResponse:
        worker_id = request.match_info.get("worker_id")
        context = self._extract_context(request)
        if worker_id:
            context["worker_id_hint"] = worker_id

        # Performing auth before handshake (breaking change but cleaner architecture)
        if self.handler:
            try:
                await self.handler("websocket_auth", None, context)
            except PermissionError as e:
                return web.Response(status=403, text=str(e))
            except Exception as e:
                return web.Response(status=500, text=str(e))

        ws = web.WebSocketResponse()
        await ws.prepare(request)

        if self.handler:
            await self.handler("websocket", ws, context)

        return ws
