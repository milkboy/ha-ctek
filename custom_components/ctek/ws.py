"""Websocket helper."""

from __future__ import annotations

import asyncio
import contextlib
from typing import TYPE_CHECKING, Any

import aiohttp
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.helpers.aiohttp_client import async_get_clientsession

if TYPE_CHECKING:
    from collections.abc import Callable

    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

from .const import BASE_LOGGER, WS_USER_AGENT

MAX_ERRORS = 10
LOGGER = BASE_LOGGER.getChild("ws")


class WebSocketClient:
    """WebSocket client for CTEK integration."""

    websocket: aiohttp.ClientWebSocketResponse | None

    def __init__(
        self, hass: HomeAssistant, entry: ConfigEntry, url: str, callback: Callable
    ) -> None:
        """Initialize the WebSocket client."""
        self.hass = hass
        self.url = url
        self.entry = entry
        self.callback = callback
        self.websocket = None
        self.session: aiohttp.ClientSession | None = None
        self._closed = False
        self._task: asyncio.Task | None = None

        # Register stop callback
        self.hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, self.stop)

    async def start(self) -> asyncio.Task:
        """Start the WebSocket client."""
        self._closed = False
        task: asyncio.Task[Any] = self.hass.async_create_background_task(
            self._run(), "CTEK WS task"
        )
        self._task = task
        return task

    async def _run(self) -> None:
        """Run loop.

        Never raises: a bare exception escaping this task makes every later
        ``await self._task`` (e.g. from :meth:`stop`) re-raise the stored
        exception, which previously broke the coordinator's WS-restart path
        permanently after a transient outage. Instead we keep retrying with
        backoff until ``stop()`` is called.
        """
        errors = 0
        while not self._closed:
            try:
                await self._connect()
                errors = 0
            except Exception:
                if self._closed:
                    return
                LOGGER.exception("WebSocket connection failed")
                errors += 1
                # Exponential-ish backoff capped at 60s; keep trying forever.
                delay = 5 if errors <= MAX_ERRORS else 60
                await asyncio.sleep(delay)

    async def _connect(self) -> None:
        """Connect to the WebSocket server and handle messages."""
        if self.session is None:
            self.session = async_get_clientsession(self.hass)

        token = self.entry.runtime_data.client.get_access_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "User-Agent": WS_USER_AGENT,
        }

        async with self.session.ws_connect(
            self.url,
            heartbeat=30,  # Send ping every 30 seconds
            timeout=aiohttp.ClientWSTimeout(ws_receive=60, ws_close=60),
            headers=headers,
        ) as websocket:
            self.websocket = websocket
            LOGGER.info("Connected to WebSocket server")

            while not self._closed:
                try:
                    # Wait for messages indefinitely
                    msg = await websocket.receive()

                    if msg.type == aiohttp.WSMsgType.TEXT:
                        try:
                            await self.callback(message=msg.data)
                        except Exception:
                            LOGGER.exception("Error processing message: %s", msg)

                    elif msg.type == aiohttp.WSMsgType.ERROR:
                        LOGGER.error(
                            "WebSocket connection closed with exception %s",
                            websocket.exception(),
                        )
                        break

                    elif msg.type in (
                        aiohttp.WSMsgType.CLOSED,
                        aiohttp.WSMsgType.CLOSING,
                        aiohttp.WSMsgType.CLOSE,
                    ):
                        LOGGER.debug("WebSocket connection closed")
                        break

                except (
                    TimeoutError,
                    aiohttp.ClientError,
                    aiohttp.WSServerHandshakeError,
                ):
                    LOGGER.exception("WebSocket error")
                    break

    async def stop(self, event: Any = None) -> None:  # noqa: ARG002
        """Stop the WebSocket client."""
        self._closed = True
        if self.websocket is not None:
            with contextlib.suppress(Exception):
                await self.websocket.close()
        if self._task is not None:
            self._task.cancel()
            # Awaiting a finished task re-raises any stored exception; we
            # don't care about either CancelledError or a prior failure here.
            with contextlib.suppress(Exception):
                await self._task

    async def running(self) -> bool:
        """Check if the WebSocket client is running."""
        return not self._closed and self._task is not None and not self._task.done()
