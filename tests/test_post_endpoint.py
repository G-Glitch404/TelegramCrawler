import json.decoder
import os
from typing import Any

import httpx
import pytest

BASE_URL = os.getenv("CRAWLER_BASE_URL", "http://localhost:9097").rstrip("/")
TEST_CHANNEL = os.getenv("TEST_TELEGRAM_CHANNEL")
TEST_LIMIT = int(os.getenv("TEST_CRAWL_LIMIT", "5"))
TEST_STOP_DATE = os.getenv("TEST_STOP_DATE")
REQUEST_TIMEOUT = float(os.getenv("TEST_REQUEST_TIMEOUT", "30"))


def _check_readiness(client: httpx.Client) -> dict[str, Any]:
    response = client.get(f"{BASE_URL}/ready")
    assert response.status_code == 200, (
        f"/ready returned HTTP {response.status_code}: {response.text}"
    )

    try: data: dict = response.json()
    except json.decoder.JSONDecodeError as exc:
        assert False, f"/ready response is not json format error {exc}"

    assert isinstance(data, dict)

    for field in ("status", "telegram_connected", "available_slots", "max_concurrent_crawls"):
        assert field in data, f"/ready response is missing {field!r}"

    return data


@pytest.fixture(scope="session")
def ready_client():
    client = httpx.Client(timeout=REQUEST_TIMEOUT)

    try: readiness = _check_readiness(client)
    except httpx.HTTPError as exc:
        client.close()
        pytest.fail(f"Could not reach TelegramCrawler at {BASE_URL}: {exc}")

    if readiness["status"] != "ready" or readiness["telegram_connected"] is not True:
        client.close()
        pytest.skip(f"TelegramCrawler is reachable but not ready: {readiness}")

    if int(readiness["available_slots"]) < 1:
        client.close()
        pytest.skip(f"TelegramCrawler has no available crawl slots: {readiness}")

    yield client
    client.close()


def test_ready_endpoint(ready_client: httpx.Client) -> None:
    readiness = _check_readiness(ready_client)

    assert readiness["status"] == "ready"
    assert readiness["telegram_connected"] is True
    assert readiness["max_concurrent_crawls"] >= 1
    assert 0 <= readiness["available_slots"] <= readiness["max_concurrent_crawls"]


@pytest.mark.skipif(
    not TEST_CHANNEL,
    reason="Set TEST_TELEGRAM_CHANNEL to run the Telegram crawl integration test.",
)
def test_crawl_channel_post(ready_client: httpx.Client) -> None:
    payload: dict[str, Any] = {"channel": TEST_CHANNEL, "limit": TEST_LIMIT}
    if TEST_STOP_DATE:
        payload["stop_date"] = TEST_STOP_DATE

    response = ready_client.post(f"{BASE_URL}/v1/crawl/channel", json=payload)
    assert response.status_code == 200, (
        f"Crawl failed with HTTP {response.status_code}: {response.text}"
    )

    body = response.json()
    assert isinstance(body, dict)
    assert body["channel"] == TEST_CHANNEL.strip("@")
    assert body["limit"] == TEST_LIMIT
    assert isinstance(body["count"], int) and body["count"] >= 0
    assert isinstance(body["elapsed_ms"], (int, float)) and body["elapsed_ms"] >= 0
    assert isinstance(body["messages"], list)
    assert len(body["messages"]) <= TEST_LIMIT
    assert body["count"] == len(body["messages"])

    required = {
        "message_id", "community", "author", "created_at", "text", "url",
        "is_forward", "has_media", "words_count", "sentiment_score",
        "engagement_count", "views", "forwards", "reactions", "message_length",
        "mention_weight", "hashtags", "cashtags", "found_urls", "engagement_hash",
    }

    for message in body["messages"]:
        assert isinstance(message, dict)
        missing = required - message.keys()
        assert not missing, f"Message is missing fields: {sorted(missing)}"
        assert isinstance(message["message_id"], int)
        assert isinstance(message["community"], str)
        assert isinstance(message["text"], str)
        assert isinstance(message["message_length"], int)
        assert isinstance(message["words_count"], int)
        assert isinstance(message["url"], str)
        assert isinstance(message["is_forward"], bool)
        assert isinstance(message["has_media"], bool)
        assert -1.0 <= float(message["sentiment_score"]) <= 1.0
        for field in ("engagement_count", "views", "forwards", "reactions", "message_length", "words_count"):
            assert isinstance(message[field], int) and message[field] >= 0
        assert 0 <= float(message["mention_weight"]) <= 5.0
        for field in ("hashtags", "cashtags", "found_urls"):
            assert isinstance(message[field], list)
        assert isinstance(message["engagement_hash"], str)
