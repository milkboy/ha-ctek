"""WebSocket client tests."""

import asyncio
import contextlib
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.ctek.ws import MAX_ERRORS, WebSocketClient


@pytest.fixture
def ws_client():
    """Create a WebSocketClient with minimal mocks."""
    hass = MagicMock()
    entry = MagicMock()
    entry.runtime_data.client.get_access_token.return_value = "token"
    callback = AsyncMock()
    return WebSocketClient(hass, entry, "wss://example.com", callback)


async def test_running_returns_false_when_task_is_done(ws_client: WebSocketClient):
    """running() returns False when the background task has completed."""
    done_task = MagicMock(spec=asyncio.Task)
    done_task.done.return_value = True
    ws_client._task = done_task
    ws_client._closed = False

    assert await ws_client.running() is False


async def test_running_returns_true_when_task_is_alive(ws_client: WebSocketClient):
    """running() returns True when the background task is still running."""
    alive_task = MagicMock(spec=asyncio.Task)
    alive_task.done.return_value = False
    ws_client._task = alive_task
    ws_client._closed = False

    assert await ws_client.running() is True


async def test_running_returns_false_when_closed(ws_client: WebSocketClient):
    """running() returns False when _closed is True regardless of task state."""
    alive_task = MagicMock(spec=asyncio.Task)
    alive_task.done.return_value = False
    ws_client._task = alive_task
    ws_client._closed = True

    assert await ws_client.running() is False


async def test_stop_unsubscribes_hass_stop_listener(ws_client: WebSocketClient):
    """stop() must release the EVENT_HOMEASSISTANT_STOP bus listener.

    Otherwise every reload leaks one listener; HA shutdown then fires .stop()
    on every dead client.
    """
    fake_unsub = MagicMock()
    ws_client._unsub_hass_stop = fake_unsub

    await ws_client.stop()

    fake_unsub.assert_called_once()


async def test_init_captures_hass_stop_unsub():
    """__init__ must store the unsub returned by async_listen_once."""
    fake_unsub = MagicMock()
    hass = MagicMock()
    hass.bus.async_listen_once = MagicMock(return_value=fake_unsub)
    entry = MagicMock()

    client = WebSocketClient(hass, entry, "wss://example.com", AsyncMock())

    assert client._unsub_hass_stop is fake_unsub


async def test_stop_returns_when_task_ignores_cancellation(
    ws_client: WebSocketClient,
):
    """stop() must not block forever if the WS task ignores cancel().

    Simulates a coroutine that swallows CancelledError (e.g. stuck inside an
    aiohttp ws_connect that doesn't honor the timeout).
    """

    async def stuck() -> None:
        try:
            await asyncio.sleep(3600)
        except asyncio.CancelledError:
            # Pretend the task ignored cancellation and kept running.
            await asyncio.sleep(3600)

    task = asyncio.create_task(stuck())
    ws_client._task = task
    ws_client.websocket = None

    await asyncio.wait_for(ws_client.stop(), timeout=10)
    # Cleanup: forcibly kill the task so the test event loop can close.
    task.cancel()
    with contextlib.suppress(BaseException):
        await task


async def test_run_does_not_raise_after_persistent_failures(
    ws_client: WebSocketClient,
):
    """_run() must not raise when persistent failures exceed MAX_ERRORS.

    A bare `raise` from _run() leaves self._task in a finished-with-exception
    state. Any later `await self._task` (e.g. from stop()) re-raises that
    exception, which previously broke coordinator.start_ws() permanently.
    """
    attempts = 0

    async def connect_stub() -> None:
        nonlocal attempts
        attempts += 1
        if attempts > MAX_ERRORS + 2:
            ws_client._closed = True
            return
        msg = "dns down"
        raise OSError(msg)

    with (
        patch.object(ws_client, "_connect", side_effect=connect_stub),
        patch("asyncio.sleep"),
    ):
        await ws_client._run()

    assert ws_client._closed is True


async def test_stop_swallows_exception_from_dead_task(
    ws_client: WebSocketClient,
):
    """stop() must not propagate exceptions stored on a finished task."""

    async def failing() -> None:
        msg = "ws task died"
        raise RuntimeError(msg)

    task = asyncio.create_task(failing())
    # Let the task actually finish with the exception stored.
    with contextlib.suppress(RuntimeError):
        await task
    assert task.done()

    ws_client._task = task
    ws_client.websocket = None

    # Must not raise.
    await ws_client.stop()


async def test_error_counter_resets_after_successful_connection(
    ws_client: WebSocketClient,
):
    """_run() must not die when total errors exceed MAX_ERRORS across a reconnect.

    Sequence: (MAX_ERRORS-1) failures, 1 success, 2 more failures.
    Without reset: cumulative errors reach MAX_ERRORS+1 and _run() raises.
    With reset: post-success errors start from 0 and _run() exits cleanly.
    """
    connect_calls: list[int] = []
    err1 = OSError("network down")
    err2 = OSError("network down again")

    async def connect_stub() -> None:
        n = len(connect_calls)
        connect_calls.append(n)
        if n < MAX_ERRORS - 1:
            raise err1
        if n == MAX_ERRORS - 1:
            return
        if n <= MAX_ERRORS + 1:
            raise err2
        ws_client._closed = True

    with (
        patch.object(ws_client, "_connect", side_effect=connect_stub),
        patch("asyncio.sleep"),
    ):
        await ws_client._run()

    assert ws_client._closed is True
