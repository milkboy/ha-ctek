"""WebSocket client tests."""

import asyncio
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
