# TelegramCrawler

A production-oriented Telegram crawling microservice built around **Telethon + FastAPI**.

TelegramCrawler connects to Telegram through an authenticated Telethon session, crawls channel messages from newest to oldest, normalizes and enriches each message, and exposes the results through a small HTTP/WebSocket API.

The service is designed to be easy to run locally, straightforward to integrate into other services, and safe to deploy as a persistent Docker service.

---

## What It Does

TelegramCrawler turns Telegram channel history into structured data that downstream applications can consume immediately.

For every crawled message, the service can expose:

- Telegram message identity and URL
- channel/community information
- author information
- message text with whitespace normalization
- creation timestamp
- forwarded/media flags
- views, forwards, reactions, and replies
- combined engagement metrics
- VADER sentiment score
- hashtags and cashtags
- contract-like addresses detected in text
- URLs found in the message
- a capped engagement-derived `mention_weight`
- an `engagement_hash` for detecting engagement changes between crawls

The service supports both **batch REST crawling** and **streaming WebSocket crawling**.

---

## Architecture

```text
                         ┌──────────────────────────┐
                         │      Client / Consumer    │
                         │ curl / Python / service   │
                         └────────────┬─────────────┘
                                      │
                           HTTP / WebSocket
                                      │
                         ┌────────────▼─────────────┐
                         │       FastAPI API         │
                         │                           │
                         │  /health                  │
                         │  /ready                   │
                         │  /v1/crawl/channel       │
                         │  /v1/ws/crawl/channel    │
                         └────────────┬─────────────┘
                                      │
                              crawl semaphore
                                      │
                         ┌────────────▼─────────────┐
                         │       Crawler Layer       │
                         │                           │
                         │ Telethon shared client    │
                         │ message extraction       │
                         │ text normalization       │
                         │ sentiment analysis       │
                         │ entity detection         │
                         │ engagement calculations  │
                         └────────────┬─────────────┘
                                      │
                                Telegram API
                                      │
                         ┌────────────▼─────────────┐
                         │        Telegram           │
                         └──────────────────────────┘
```

The API layer handles HTTP/WebSocket concerns while Telegram-specific crawling and message processing remain in the crawler layer.

---

## Project Structure

A typical project layout is:

```text
TelegramCrawler/
├── src/
│   ├── __init__.py
│   ├── api.py
│   ├── crawler.py
│   ├── items.py
│   └── main.py
├── .env/
│   ├── .env.dev
│   └── .env.prod
├── session/
│   └── telegram_crawler.session
├── Dockerfile
├── docker-compose.yml
├── pyproject.toml
├── uv.lock
├── pytest.ini
└── README.md
```

Do not commit secrets or Telegram session files.

Recommended `.gitignore` entries:

```gitignore
.env/
*.session
*.session-journal
session/
.venv/
__pycache__/
.pytest_cache/
```

---

# Requirements

## Runtime

- Python 3.12+
- [uv](https://docs.astral.sh/uv/)
- Docker / Docker Compose for container deployment
- Telegram API credentials
- An authenticated Telethon session file

## Python stack

The application is built around:

- FastAPI
- Uvicorn
- Telethon
- Pydantic
- `python-dotenv`
- `vaderSentiment`
- `httpx` for HTTP integrations/tests
- `websockets` for WebSocket clients

Dependencies are defined and locked through `pyproject.toml` and `uv.lock`.

---

# Telegram API Credentials

TelegramCrawler uses a Telethon client and therefore needs Telegram API credentials.

Create your own Telegram application through Telegram's developer tools and obtain:

```text
TELEGRAM_APP_ID
TELEGRAM_API_HASH
```

These values are sensitive. Never commit them to Git or expose them in public logs, source code, screenshots, or container images.

---

# Environment Configuration

TelegramCrawler is environment-driven.

A local development environment can look like:

```dotenv
TELEGRAM_APP_ID=12345678
TELEGRAM_API_HASH=your_api_hash
TELEGRAM_SESSION_PATH=./session/telegram_crawler.session

HOST=0.0.0.0
PORT=9097

MAX_CONCURRENT_CRAWLS=2
DEFAULT_TIMEOUT_SECONDS=180
```

## Environment Variables

| Variable | Purpose | Example / Default |
| --- | --- | --- |
| `TELEGRAM_APP_ID` | Telegram application ID | `12345678` |
| `TELEGRAM_API_HASH` | Telegram application hash | secret value |
| `TELEGRAM_SESSION_PATH` | Path to the Telethon session file | `./session/telegram_crawler.session` locally; `/app/session/telegram_crawler.session` in Docker |
| `HOST` | API bind address | `0.0.0.0` |
| `PORT` | API port | `9097` |
| `MAX_CONCURRENT_CRAWLS` | Maximum simultaneous crawl operations | `2` |
| `DEFAULT_TIMEOUT_SECONDS` | Default application timeout configuration | `180` |

The exact environment files are intentionally outside source control.

---

# The Telethon Session Is Mandatory

The crawler needs an **authenticated Telethon session**.

You have two supported ways to obtain it:

1. Bring your own existing `.session` file.
2. Generate one yourself by running `src/crawler.py` with `uv` and explicitly injecting the environment file.

A session file represents authenticated Telegram client state. Treat it like a credential.

## Generate the Session Locally

Create a development environment file with a writable local session path, for example:

```dotenv
TELEGRAM_APP_ID=12345678
TELEGRAM_API_HASH=your_api_hash
TELEGRAM_SESSION_PATH=./session/telegram_crawler.session
```

Then make sure the session directory exists:

```bash
mkdir -p session
```

Run the crawler entry point through `uv` and **inject the environment file**:

```bash
uv run --env-file .env/.env.dev src/crawler.py
```

> The `--env-file` part is important. It ensures the crawler receives the Telegram credentials and session path from the environment file rather than relying on whatever happens to be exported in your shell.

On first authentication, Telethon will request the information required to authenticate the Telegram account. After successful authentication, the session is stored at the configured `TELEGRAM_SESSION_PATH`.

Once the session exists, the API can reuse it without requiring a new login every time the service starts.

### Verify the session file

For the example configuration:

```bash
ls -lh session/telegram_crawler.session
```

If you already have a valid session file, do not regenerate it unnecessarily; point `TELEGRAM_SESSION_PATH` to the existing file instead.

---

# Local Development

## Install / Sync Dependencies

From the project root:

```bash
uv sync
```

## Run the API

Use the environment file explicitly:

```bash
uv run --env-file .env/.env.dev python -m src.main
```

The API will normally be available at:

```text
http://localhost:9097
```

Using `uv run` is recommended because it runs the application inside the project's managed environment and keeps dependencies synchronized with the lockfile.

---

# API Overview

| Method | Endpoint | Description |
| --- | --- | --- |
| `GET` | `/health` | Process/liveness check |
| `GET` | `/ready` | Telegram readiness and crawl capacity |
| `POST` | `/v1/crawl/channel` | Crawl a channel and return the full batch |
| `WS` | `/v1/ws/crawl/channel` | Stream messages as they are discovered |

FastAPI also exposes interactive API documentation:

- Swagger UI: `http://localhost:9097/docs`
- ReDoc: `http://localhost:9097/redoc`
- OpenAPI JSON: `http://localhost:9097/openapi.json`

---

# `GET /health`

A lightweight liveness endpoint.

It answers whether the application process is alive. It should not perform a Telegram crawl.

## Request

```bash
curl http://localhost:9097/health
```

## Example Response

```json
{
  "status": "healthy",
  "service": "telegram-crawler",
  "version": "1.0.0"
}
```

Use this endpoint for basic service checks and container health monitoring.

---

# `GET /ready`

Readiness is different from liveness.

A healthy process can still be unable to crawl Telegram if the Telethon client is disconnected or initialization has failed.

## Request

```bash
curl http://localhost:9097/ready
```

## Ready Response

```json
{
  "status": "ready",
  "telegram_connected": true,
  "available_slots": 2,
  "max_concurrent_crawls": 2
}
```

## Not Ready Response

```json
{
  "status": "not_ready",
  "telegram_connected": false,
  "available_slots": 2,
  "max_concurrent_crawls": 2
}
```

`available_slots` is the current crawl capacity, while `max_concurrent_crawls` is the configured upper bound.

---

# `POST /v1/crawl/channel`

The primary REST endpoint.

It crawls one Telegram channel from newest to oldest and returns a complete response after the crawl finishes.

## Request Body

```json
{
  "channel": "examplechannel",
  "limit": 100,
  "stop_date": "2026-08-01"
}
```

### `channel`

Telegram channel handle.

Both forms are accepted:

```text
examplechannel
```

and:

```text
@examplechannel
```

The service normalizes the channel when constructing Telegram message URLs.

### `limit`

Maximum number of messages to return.

Example:

```json
{
  "channel": "examplechannel",
  "limit": 25
}
```

### `stop_date`

Optional historical crawl boundary in `YYYY-MM-DD` format.

The crawler starts with recent messages and walks backwards. Once it reaches a message whose date is older than `stop_date`, it stops instead of continuing through older history.

Example:

```json
{
  "channel": "examplechannel",
  "limit": 1000,
  "stop_date": "2026-08-01"
}
```

Conceptually:

```text
newest
  │
  ├── 2026-08-03  ← crawl
  ├── 2026-08-02  ← crawl
  ├── 2026-08-01  ← crawl
  ├── 2026-07-31  ← older than stop_date → stop
  │
  └── older history is not traversed
```

This makes `stop_date` useful for bounded historical crawls and avoids unnecessarily traversing older messages.

## Minimal Request

```bash
curl -X POST http://localhost:9097/v1/crawl/channel \
  -H 'Content-Type: application/json' \
  -d '{
    "channel": "examplechannel",
    "limit": 10
  }'
```

## Historical Crawl

```bash
curl -X POST http://localhost:9097/v1/crawl/channel \
  -H 'Content-Type: application/json' \
  -d '{
    "channel": "examplechannel",
    "limit": 500,
    "stop_date": "2026-08-01"
  }'
```

## Example Response

```json
{
  "channel": "examplechannel",
  "limit": 100,
  "count": 2,
  "elapsed_ms": 842,
  "messages": [
    {
      "message_id": "examplechannel_12345",
      "community": "examplechannel",
      "author": "Example Channel",
      "created_at": "2026-08-01T12:30:00+00:00",
      "text": "BTC is breaking out and this looks extremely bullish",
      "message_length": 51,
      "words_count": 5,
      "words_length": 29,
      "url": "https://t.me/examplechannel/12345",
      "is_forward": false,
      "has_media": false,
      "sentiment_score": 0.4404,
      "engagement_count": 1250,
      "views": 1000,
      "forwards": 100,
      "reactions": 100,
      "message_weight": 1.5,
      "hashtags": [
        "crypto"
      ],
      "cashtags": [
        "BTC"
      ],
      "found_urls": [
        "https://example.com"
      ],
      "engagement_hash": "..."
    }
  ]
}
```

The values above are illustrative; actual values come from Telegram and the crawler's processing logic.

---

# Telegram Message Schema

Each item in `messages` represents one processed Telegram message.

| Field              | Meaning                                                                                                        |
|--------------------|----------------------------------------------------------------------------------------------------------------|
| `message_id`       | Stable application-level identifier combining the channel and Telegram message ID, e.g. `examplechannel_12345` |
| `community`        | Normalized Telegram channel handle                                                                             |
| `author`           | Telegram post author when available                                                                            |
| `created_at`       | Telegram message creation timestamp                                                                            |
| `text`             | Normalized message text                                                                                        |
| `message_length`   | Length of normalized message text                                                                              |
| `words_count`      | amount of words in the message text with more than 3 chars                                                     |
| `words_length`     | amount of charactars in the found words in the message text with more than 3 chars                             |
| `url`              | Direct Telegram message URL                                                                                    |
| `is_forward`       | Whether the message is a forwarded post                                                                        |
| `has_media`        | Whether Telegram reports media on the message                                                                  |
| `sentiment_score`  | VADER compound sentiment score, from `-1.0` to `1.0`                                                           |
| `engagement_count` | Combined views + forwards + reactions + replies                                                                |
| `views`            | Telegram view count                                                                                            |
| `forwards`         | Telegram forward count                                                                                         |
| `reactions`        | Total reaction count                                                                                           |
| `message_weight`   | Engagement-derived weight capped at `5.0`                                                                      |
| `hashtags`         | Hashtags extracted from Telegram message entities                                                              |
| `cashtags`         | Cashtags such as `BTC` or `ETH` detected in the message                                                        |
| `found_urls`       | URLs detected in the message                                                                                   |
| `engagement_hash`  | Hash representing engagement values and useful for engagment metric change detection                           |
| `content_hash`     | Hash representing content values and useful for text change detection                                          |

---

# Text Normalization

Messages are normalized before downstream processing.

The crawler:

- removes zero-width spaces
- collapses repeated whitespace
- strips leading and trailing whitespace

For example:

```text
BTC    is
moving   higher
```

becomes:

```text
BTC is moving higher
```

This makes downstream text processing and message comparisons more stable.

---

# Sentiment Analysis

The crawler uses VADER sentiment analysis.

The `sentiment_score` is the VADER compound score:

```text
-1.0  ← strongly negative
 0.0  ← neutral / approximately neutral
+1.0  ← strongly positive
```

For example, a strongly bullish message can receive a positive compound score, while strongly negative language produces a negative score.

The raw score is returned in the API response so downstream systems can apply their own thresholds.

---

# Engagement Metrics

The crawler extracts the engagement signals exposed by Telegram, including:

- views
- forwards
- reactions
- replies

The combined engagement value is:

```text
engagement_count = views + forwards + reactions + replies
```

Example:

```text
views     = 1000
forwards  = 20
reactions = 50
replies   = 10
----------------
engagement_count = 1080
```

## Engagement Hash

The crawler generates an engagement hash from the engagement values:

```text
views|forwards|reactions|replies
```

The hash can be stored downstream and compared during a later crawl. If the hash changes, one or more engagement values changed.

This is useful when repeatedly crawling the same channel and wanting to detect message engagement updates without treating the entire message as new.

---

# `mention_weight`

`mention_weight` is an engagement-derived value that combines a configured channel weight with observed engagement.

The current calculation is conceptually:

```text
channel_weight
+ views / 10000
+ forwards / 100
+ reactions / 200
+ replies / 50
```

The resulting value is capped at:

```text
5.0
```

This field is intended as a downstream prioritization signal rather than a raw Telegram metric.

---

# WebSocket Streaming API

## `WS /v1/ws/crawl/channel`

The WebSocket endpoint performs the same basic channel-crawling operation but sends messages individually as they are discovered.

This is useful when a consumer should begin processing immediately rather than wait for a potentially large REST response.

## Connection

```text
ws://localhost:9097/v1/ws/crawl/channel
```

## Send Crawl Parameters

After connecting, send JSON such as:

```json
{
  "channel": "examplechannel",
  "limit": 100,
  "stop_date": "2026-08-01"
}
```

## Item Event

A message event has the form:

```json
{
  "type": "item",
  "data": {
    "message_id": "examplechannel_12345",
    "community": "examplechannel",
    "text": "Example Telegram message"
  }
}
```

The full message object is supplied in `data` by the actual service.

## Completion Event

When the crawl finishes:

```json
{
  "type": "done"
}
```

## Error Event

If a streaming crawl fails:

```json
{
  "type": "error",
  "detail": "Telegram client is not connected"
}
```

## Python Example

```python
import json

import websockets


async def stream_channel() -> None:
    async with websockets.connect(
        "ws://localhost:9097/v1/ws/crawl/channel"
    ) as websocket:
        await websocket.send(
            json.dumps(
                {
                    "channel": "examplechannel",
                    "limit": 100,
                    "stop_date": "2026-08-01",
                }
            )
        )

        async for raw_message in websocket:
            data = json.loads(raw_message)

            if data["type"] == "item":
                process(data["data"])
            elif data["type"] == "done":
                break
            elif data["type"] == "error":
                raise RuntimeError(data["detail"])
```

---

# REST Client Example

A simple asynchronous Python consumer can use `httpx`:

```python
import httpx


async def crawl_channel() -> dict:
    async with httpx.AsyncClient(timeout=60) as client:
        response = await client.post(
            "http://localhost:9097/v1/crawl/channel",
            json={
                "channel": "examplechannel",
                "limit": 100,
                "stop_date": "2026-08-01",
            },
        )
        response.raise_for_status()
        return response.json()
```

---

# Concurrency

Crawl operations are protected by a concurrency semaphore.

For example:

```dotenv
MAX_CONCURRENT_CRAWLS=2
```

allows two crawl operations to run simultaneously.

If all slots are occupied, additional crawl requests wait for an available slot instead of creating an unlimited number of simultaneous Telegram operations.

The current capacity is visible through `/ready`:

```json
{
  "status": "ready",
  "telegram_connected": true,
  "available_slots": 1,
  "max_concurrent_crawls": 2
}
```

This is particularly useful for orchestration and monitoring.

---

# Docker Deployment

Docker is the recommended production deployment method.

The supplied Docker image uses Python 3.12, `uv`, and Uvicorn and starts the application with:

```text
uv run uvicorn src.main:app --host 0.0.0.0 --port 9097
```

The container also uses `tini` as PID 1 and creates `/app/session` for persistent Telethon session storage.

## 1. Prepare the Production Environment File

Create:

```text
.env/.env.prod
```

Example:

```dotenv
TELEGRAM_APP_ID=12345678
TELEGRAM_API_HASH=your_api_hash
TELEGRAM_SESSION_PATH=/app/session/telegram_crawler.session

HOST=0.0.0.0
PORT=9097
MAX_CONCURRENT_CRAWLS=2
DEFAULT_TIMEOUT_SECONDS=180
```

Make sure the session referenced by `TELEGRAM_SESSION_PATH` is available to the container through the persistent Docker volume.

## 2. Make Sure the External Docker Network Exists

The Compose configuration expects an external network called `crawlers-network`.

Create it once if it does not already exist:

```bash
docker network create crawlers-network
```

If it already exists, Docker will report that fact; that is fine.

## 3. Build and Start the Service

### Important

The production environment file must be supplied to **Docker Compose itself** for Compose variable interpolation.

Use this exact command:

```bash
docker compose --env-file .env/.env.prod up -d --build
```

**Do not put `--env-file` after `up`.** The correct order is:

```text
docker compose --env-file <env-file> up ...
             └──────────────┘
              Compose option
```

The command above is the canonical production start command for this project.

## Why `--env-file` Matters

Docker Compose has two separate concepts:

1. `env_file:` supplies environment variables to the container.
2. `--env-file` supplies variables to Compose while it evaluates `${...}` expressions in the Compose file.

For example, the Compose file may contain:

```yaml
ports:
  - "${PORT:-9097}:9097"
```

and:

```yaml
environment:
  TELEGRAM_APP_ID: ${TELEGRAM_APP_ID}
  TELEGRAM_API_HASH: ${TELEGRAM_API_HASH}
```

Therefore the production file should be explicitly provided to Compose:

```bash
docker compose --env-file .env/.env.prod up -d --build
```

This avoids warnings such as:

```text
The "TELEGRAM_APP_ID" variable is not set.
The "TELEGRAM_API_HASH" variable is not set.
The "HOST" variable is not set.
The "PORT" variable is not set.
```

---

# Docker Compose Lifecycle

## Start

```bash
docker compose --env-file .env/.env.prod up -d --build
```

## Show Containers

```bash
docker compose ps
```

## Follow Logs

```bash
docker compose logs -f telegram-crawler
```

## Restart

```bash
docker compose restart telegram-crawler
```

## Rebuild After Code Changes

```bash
docker compose --env-file .env/.env.prod up -d --build
```

## Stop

```bash
docker compose down
```

> `down` removes the containers but does not remove named volumes unless explicitly requested. The named `telegram_session` volume is intended to preserve Telegram authentication state across normal container recreation.

## Check Health

```bash
curl http://localhost:9097/health
```

## Check Telegram Readiness

```bash
curl http://localhost:9097/ready
```

---

# Docker Session Persistence

The Compose deployment mounts the named Docker volume:

```yaml
volumes:
  - telegram_session:/app/session
```

The purpose is to keep the Telethon session outside the disposable application container.

Without persistent storage, destroying and recreating the container could also destroy the session and force Telegram authentication again.

Do not casually delete the session volume in production.

---

# Production Checklist

Before starting a production deployment:

```text
[ ] Telegram API ID is configured
[ ] Telegram API hash is configured
[ ] Authenticated Telethon session exists
[ ] TELEGRAM_SESSION_PATH is correct
[ ] .env/.env.prod is not committed to Git
[ ] crawlers-network exists
[ ] Docker Compose command uses --env-file before up
[ ] /health responds successfully
[ ] /ready reports telegram_connected=true
[ ] Session storage is persistent
```

Recommended startup flow:

```text
Telegram credentials
        │
        ▼
Generate / provide session
        │
        ▼
.env/.env.prod
        │
        ▼
Docker Compose
        │
        ▼
TelegramCrawler
        │
        ├── /health
        ├── /ready
        ├── REST crawl
        └── WebSocket crawl
```

---

# Testing

The integration tests use the running TelegramCrawler API rather than starting the API server themselves.

The test environment can define values such as:

```dotenv
CRAWLER_BASE_URL=http://localhost:9097
TEST_TELEGRAM_CHANNEL=examplechannel
TEST_CRAWL_LIMIT=5
TEST_STOP_DATE=2026-08-01
TEST_REQUEST_TIMEOUT=30
```

Run the tests through `uv`:

```bash
uv run --env-file .env/.env.test pytest
```

To run one test file with verbose output:

```bash
uv run --env-file .env/.env.test pytest tests/test_post_endpoint.py -vv -s
```

The test suite verifies readiness and the REST crawl contract, including response fields and message structure.

If the integration test is skipped, check that the test environment contains `TEST_TELEGRAM_CHANNEL`.

---

# Common Problems

## Compose says environment variables are not set

If you see warnings such as:

```text
The "TELEGRAM_APP_ID" variable is not set.
```

start Compose with the environment file supplied to Compose itself:

```bash
docker compose --env-file .env/.env.prod up -d --build
```

## `/health` works but `/ready` is not ready

A healthy API process does not necessarily mean Telegram is available.

Check:

```bash
curl http://localhost:9097/ready
```

Then inspect logs:

```bash
docker compose logs -f telegram-crawler
```

Common causes are missing Telegram credentials, an invalid/missing session, or Telegram connectivity/authentication problems.

## The session file is not found in Docker

Check the effective environment and confirm that `TELEGRAM_SESSION_PATH` points into the mounted session directory, for example:

```text
/app/session/telegram_crawler.session
```

The Compose volume should be mounted at:

```text
/app/session
```

## The API returns a crawl error / `502`

A crawl request can fail even when the FastAPI process itself is reachable.

Check `/ready` and the container logs first:

```bash
curl http://localhost:9097/ready
docker compose logs -f telegram-crawler
```

A server-side crawl failure generally indicates a problem with the Telegram operation or message processing path rather than the HTTP client itself.

## Port 9097 is already in use

Either stop the process currently using the port or configure another host port in the Compose environment.

For example:

```dotenv
PORT=9098
```

Then restart:

```bash
docker compose --env-file .env/.env.prod up -d --build
```

The container itself continues to listen on port `9097`; the configured value controls the published host port in the Compose mapping.

---

# Design Notes

## One Channel Per Crawl Request

The service intentionally uses one primary crawl operation:

```text
POST /v1/crawl/channel
```

Recent crawling, historical crawling, and bounded crawling are represented through request parameters such as `limit` and `stop_date` rather than separate endpoints.

Multiple channels can be handled by the calling application with multiple requests while the service controls concurrency centrally.

## REST vs WebSocket

Use REST when the consumer wants one complete result:

```text
request → crawl → complete response
```

Use WebSockets when the consumer wants incremental processing:

```text
request
  ↓
item 1
  ↓
item 2
  ↓
item 3
  ↓
...
  ↓
done
```

This distinction is particularly useful for large crawls, real-time downstream pipelines, notifications, token detection, and event processing.

## Persistent Authentication State

The Telethon session is deliberately treated as persistent application state. The API container can be replaced while the authenticated session remains available through persistent storage.

---

# Security

Treat the following as secrets:

```text
TELEGRAM_APP_ID
TELEGRAM_API_HASH
*.session
*.session-journal
```

In particular, the Telethon session should be considered equivalent to an authenticated Telegram client state.

Do not:

- commit `.env/.env.prod`
- commit session files
- copy session files into public Docker images
- paste API hashes or session contents into issue trackers
- expose the API publicly without appropriate network controls and authentication

If the API is deployed outside a trusted network, put it behind the appropriate reverse proxy, access control, firewall rules, or service-to-service authentication.

---

# Quick Start

For a new deployment, the shortest reliable path is:

### 1. Configure Telegram credentials

```dotenv
TELEGRAM_APP_ID=...
TELEGRAM_API_HASH=...
TELEGRAM_SESSION_PATH=./session/telegram_crawler.session
```

### 2. Generate the session

```bash
mkdir -p session
uv run --env-file .env/.env.dev python3 src.crawler
```

### 3. Create the Docker network if required

```bash
docker network create crawlers-network
```

### 4. Configure production environment

```text
.env/.env.prod
```

with a Docker path such as:

```dotenv
TELEGRAM_SESSION_PATH=/app/session/telegram_crawler.session
```

### 5. Start production

```bash
docker compose --env-file .env/.env.prod up -d --build
```

### 6. Verify

```bash
curl http://localhost:9097/health
curl http://localhost:9097/ready
```

### 7. Crawl a channel

```bash
curl -X POST http://localhost:9097/v1/crawl/channel \
  -H 'Content-Type: application/json' \
  -d '{
    "channel": "examplechannel",
    "limit": 10,
    "stop_date": "2026-08-01"
  }'
```

---

# API Documentation at Runtime

When the service is running, the generated API contract is available directly from FastAPI:

```text
Swagger UI
http://localhost:9097/docs
```

```text
ReDoc
http://localhost:9097/redoc
```

```text
OpenAPI
http://localhost:9097/openapi.json
```

These endpoints are the best place to inspect the exact request/response schema exposed by the current build.

---

# License
- MIT
