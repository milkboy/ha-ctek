"""Websocket helper."""

import asyncio
import contextlib
from collections.abc import Callable
from typing import Any

import aiohttp
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import LOGGER, WS_USER_AGENT

MAX_ERRORS = 10


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
        """Run loop."""
        errors = 0
        while not self._closed:
            try:
                await self._connect()
            except Exception as err:
                if not self._closed:
                    LOGGER.error("WebSocket connection failed: %s", err)
                    errors += 1
                    if errors > MAX_ERRORS:
                        raise Exception from err  # noqa: TRY002
                    await asyncio.sleep(5)  # Wait before reconnecting

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
            timeout=60,  # Connection timeout
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
                        except Exception:  # noqa: BLE001
                            LOGGER.error("Error processing message: %s", msg)

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
                ) as err:
                    LOGGER.error("WebSocket error: %s", err)
                    break

    async def stop(self, event: Any = None) -> None:  # noqa: ARG002
        """Stop the WebSocket client."""
        self._closed = True
        if self.websocket is not None:
            await self.websocket.close()
        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
