# -------------------------------------------------------------------------------------------------
#  Copyright (C) 2015-2026 Nautech Systems Pty Ltd. All rights reserved.
#  https://nautechsystems.io
#
#  Licensed under the GNU Lesser General Public License Version 3.0 (the "License");
#  You may not use this file except in compliance with the License.
#  You may obtain a copy of the License at https://www.gnu.org/licenses/lgpl-3.0.en.html
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
# -------------------------------------------------------------------------------------------------

import asyncio
from typing import Any

import pytest

from nautilus_trader.adapters.binance.websocket.client import BinanceWebSocketClient
from nautilus_trader.common.component import LiveClock


@pytest.fixture
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


def _make_client(event_loop: asyncio.AbstractEventLoop) -> BinanceWebSocketClient:
    return BinanceWebSocketClient(
        clock=LiveClock(),
        base_url="wss://example.invalid/market",
        handler=lambda _: None,
        handler_reconnect=None,
        loop=event_loop,
    )


def _mark_client_connected(client: BinanceWebSocketClient, client_id: int = 0) -> None:
    client._clients[client_id] = object()
    client._client_streams[client_id] = []
    client._is_connecting[client_id] = False
    client._next_client_id = max(client._next_client_id, client_id + 1)


def test_connected_subscriptions_are_sent_as_one_batch(event_loop):
    client = _make_client(event_loop)
    _mark_client_connected(client)
    sent: list[tuple[int, dict[str, Any]]] = []

    async def fake_send(client_id: int, msg: dict[str, Any]) -> None:
        sent.append((client_id, msg))

    client._send = fake_send

    event_loop.run_until_complete(client._subscribe("btcusdt@kline_4h"))
    event_loop.run_until_complete(client._subscribe("ethusdt@kline_4h"))
    event_loop.run_until_complete(client._subscribe("solusdt@kline_4h"))
    event_loop.run_until_complete(
        asyncio.sleep(client.SUBSCRIBE_BATCH_DELAY_SECONDS + 0.05),
    )

    assert sent == [
        (
            0,
            {
                "method": "SUBSCRIBE",
                "params": [
                    "btcusdt@kline_4h",
                    "ethusdt@kline_4h",
                    "solusdt@kline_4h",
                ],
                "id": 0,
            },
        ),
    ]
    assert client.subscriptions == [
        "btcusdt@kline_4h",
        "ethusdt@kline_4h",
        "solusdt@kline_4h",
    ]


def test_first_subscription_still_connects_immediately(event_loop):
    client = _make_client(event_loop)
    connected: list[tuple[int, list[str]]] = []

    async def fake_connect(client_id: int, streams: list[str]) -> None:
        connected.append((client_id, streams.copy()))
        client._clients[client_id] = object()

    client._connect_client = fake_connect

    event_loop.run_until_complete(client._subscribe("btcusdt@kline_4h"))

    assert connected == [(0, ["btcusdt@kline_4h"])]
    assert client.subscriptions == ["btcusdt@kline_4h"]


def test_unsubscribe_removes_stream_from_pending_subscribe_batch(event_loop):
    client = _make_client(event_loop)
    _mark_client_connected(client)
    sent: list[tuple[int, dict[str, Any]]] = []
    disconnected: list[int] = []

    async def fake_send(client_id: int, msg: dict[str, Any]) -> None:
        sent.append((client_id, msg))

    async def fake_disconnect(client_id: int) -> None:
        disconnected.append(client_id)
        client._clients[client_id] = None

    client._send = fake_send
    client._disconnect_client = fake_disconnect

    event_loop.run_until_complete(client._subscribe("btcusdt@kline_4h"))
    event_loop.run_until_complete(client._unsubscribe("btcusdt@kline_4h"))
    event_loop.run_until_complete(
        asyncio.sleep(client.SUBSCRIBE_BATCH_DELAY_SECONDS + 0.05),
    )

    assert sent == []
    assert disconnected == [0]
    assert client.subscriptions == []
