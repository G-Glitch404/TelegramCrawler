import asyncio
import json
import os

import httpx
import pytest
import websockets

from typing import Any


HTTP_BASE_URL = os.getenv("CRAWLER_BASE_URL", "http://localhost:9097").rstrip("/")
WS_BASE_URL = HTTP_BASE_URL.replace("https://", "wss://", 1).replace("http://", "ws://", 1)
WS_PATH = "/v1/ws/crawl/channel"
TEST_CHANNEL = os.getenv("TEST_TELEGRAM_CHANNEL")
TEST_LIMIT = int(os.getenv("TEST_CRAWL_LIMIT", "5"))
TEST_STOP_DATE = os.getenv("TEST_STOP_DATE")
HTTP_TIMEOUT = float(os.getenv("TEST_REQUEST_TIMEOUT", "30"))
WS_TIMEOUT = float(os.getenv("TEST_WS_TIMEOUT", "45"))


def _check_readiness() -> dict[str, Any]:
    with httpx.Client(timeout=HTTP_TIMEOUT) as client:
        response = client.get(f"{HTTP_BASE_URL}/ready")

    assert response.status_code == 200, (
        f"/ready returned HTTP {response.status_code}: {response.text}"
    )

    data = response.json()
    assert isinstance(data, dict)

    for field in ("status", "telegram_connected", "available_slots", "max_concurrent_crawls"):
        assert field in data, f"/ready response is missing {field!r}"

    return data


@pytest.fixture(scope="session")
def websocket_ready():
    try: readiness = _check_readiness()
    except httpx.HTTPError as exc:
        pytest.fail(f"Could not reach TelegramCrawler at {HTTP_BASE_URL}: {exc}")

    if readiness["status"] != "ready" or readiness["telegram_connected"] is not True:
        pytest.skip(f"TelegramCrawler is reachable but not ready: {readiness}")
    if int(readiness["available_slots"]) < 1:
        pytest.skip(f"TelegramCrawler has no available crawl slots: {readiness}")

    return readiness


def _payload() -> dict[str, Any]:
    payload: dict[str, Any] = {"channel": TEST_CHANNEL, "limit": TEST_LIMIT}
    if TEST_STOP_DATE:
        payload["stop_date"] = TEST_STOP_DATE
    return payload


@pytest.mark.skipif(
    not TEST_CHANNEL,
    reason="Set TEST_TELEGRAM_CHANNEL to run the WebSocket crawl integration test.",
)
def test_crawl_channel_websocket(websocket_ready) -> None:
    async def run() -> None:
        items: list[dict[str, Any]] = []
        done_seen = False

        async with websockets.connect(
            f"{WS_BASE_URL}{WS_PATH}",
            open_timeout=WS_TIMEOUT,
            close_timeout=WS_TIMEOUT,
            ping_timeout=WS_TIMEOUT,
            max_size=4 * 1024 * 1024,
        ) as websocket:
            await websocket.send(json.dumps(_payload()))

            while True:
                raw = await asyncio.wait_for(websocket.recv(), timeout=WS_TIMEOUT)
                assert isinstance(raw, str), "Expected text JSON WebSocket messages"
                event = json.loads(raw)
                assert isinstance(event, dict)
                assert "type" in event

                event_type = event["type"]
                if event_type == "item":
                    data = event.get("data")
                    assert isinstance(data, dict)
                    assert isinstance(data.get("message_id"), int)
                    assert isinstance(data.get("community"), str)
                    assert isinstance(data.get("text"), str)
                    items.append(data)
                    assert len(items) <= TEST_LIMIT
                elif event_type == "done":
                    done_seen = True
                    break
                elif event_type == "error":
                    pytest.fail(f"TelegramCrawler WebSocket error: {event.get('detail', 'Unknown error')}")
                else:
                    pytest.fail(f"Unexpected WebSocket event type: {event_type!r}")

        assert done_seen is True
        assert len(items) <= TEST_LIMIT

    asyncio.run(run())
