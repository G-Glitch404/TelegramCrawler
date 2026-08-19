# TelegramCrawler

A container-first FastAPI microservice for crawling Telegram channels with Telethon.

TelegramCrawler is designed as a small scraping service that isolates Telegram crawling from the rest of your application. It exposes health, readiness, and channel crawling endpoints and keeps the crawler implementation separate from the HTTP API.

## Features

- Telegram channel crawling through Telethon
- FastAPI HTTP API
- Single channel crawl endpoint
- WebSocket streaming for real-time message delivery
- Health and readiness endpoints
- Configurable crawl concurrency
- `stop_date` support
- Message sentiment analysis using VADER
- Engagement extraction
- Hashtag, cashtag, contract, and URL extraction
- Docker-friendly runtime
- No application logging framework required
- Shared crawler implementation for HTTP and WebSocket clients

## Architecture

```text
Client
  |
  +-- GET /health
  |
  +-- GET /ready
  |
  +-- POST /v1/crawl/channel
  |
  +-- WS /v1/ws/crawl/channel
  |
  v
FastAPI
  |
  v
TelegramCrawler
  |
  v
Telethon
  |
  v
Telegram API
```

The crawler is responsible for Telegram-specific functionality while FastAPI is responsible for request validation, concurrency control, HTTP/WebSocket communication, and response formatting.

# TelegramCrawler

## Project Structure

```text
TelegramCrawler/
├── src/
│   ├── __init__.py
│   ├── api.py
│   ├── crawler.py
│   ├── items.py
│   └── main.py
├── .env
├── Dockerfile
├── pyproject.toml
└── README.md
```

## Requirements

You need:

- Python 3.12+
- Telegram API credentials
- A Telegram session
- Telethon
- FastAPI
- Uvicorn
- Pydantic
- `python-dotenv`
- `vaderSentiment`

Telegram API credentials are obtained from Telegram's developer portal.

## Environment Variables

Example `.env`:

```dotenv
TELEGRAM_APP_ID=12345678
TELEGRAM_API_HASH=your_api_hash
TELEGRAM_SESSION_PATH=./session/telegram_crawler.session

HOST=0.0.0.0
PORT=9097

MAX_CONCURRENT_CRAWLS=2
DEFAULT_TIMEOUT_SECONDS=120
```

### `TELEGRAM_APP_ID`

Your Telegram application ID.

### `TELEGRAM_API_HASH`

Your Telegram application hash.

### `TELEGRAM_SESSION_PATH`

Path to the Telethon session file.

The session is important because it stores the authenticated Telegram client state.

### `HOST`

API bind address.

Default:

```text
0.0.0.0
```

### `PORT`

API port.

Default:

```text
9097
```

### `MAX_CONCURRENT_CRAWLS`

Maximum number of simultaneous crawl operations.

Example:

```dotenv
MAX_CONCURRENT_CRAWLS=2
```

### `DEFAULT_TIMEOUT_SECONDS`

Default timeout used by the API when a request does not specify another timeout.

## Authentication

TelegramCrawler uses a Telethon client.

The crawler creates one shared client:

```python
_client = TelegramClient(
    session=...,
    api_id=settings["TELEGRAM_APP_ID"],
    api_hash=settings["TELEGRAM_API_HASH"],
)
```

The session must already be authenticated before the crawler can access channels that require an authenticated Telegram account.

The first authentication can be performed with Telethon using your Telegram account. Once the session file has been created, the service can reuse it.

Do not commit the session file to Git.

Example `.gitignore`:

```gitignore
.env
session/
*.session
*.session-journal
__pycache__/
.pytest_cache/
```

## Running the Service

Start the API with:

```bash
python -m src.main
```

The default server is:

```text
http://127.0.0.1:9097
```

When bound to `0.0.0.0`, the service listens on all container interfaces.

## Main API

The service exposes three HTTP endpoints:

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `GET` | `/health` | Liveness |
| `GET` | `/ready` | Readiness |
| `POST` | `/v1/crawl/channel` | Crawl a Telegram channel |

A WebSocket endpoint is also provided for streaming crawls.

## Health

### `GET /health`

The health endpoint answers whether the application process is alive.

Example:

```bash
curl http://localhost:9097/health
```

Example response:

```json
{
  "status": "healthy",
  "service": "telegram-crawler",
  "version": "1.0.0"
}
```

The health endpoint should remain lightweight and should not perform a Telegram crawl.

## Readiness

### `GET /ready`

The readiness endpoint determines whether the service is ready to perform Telegram operations.

Example:

```bash
curl http://localhost:9097/ready
```

Example response:

```json
{
  "status": "ready",
  "telegram_connected": true,
  "available_slots": 2,
  "max_concurrent_crawls": 2
}
```

If the Telegram client is not connected:

```json
{
  "status": "not_ready",
  "telegram_connected": false,
  "available_slots": 2,
  "max_concurrent_crawls": 2
}
```

The readiness endpoint is useful for Docker health checks, orchestration systems, and deployment systems.

## Crawl Channel

### `POST /v1/crawl/channel`

Crawls messages from one Telegram channel.

Example request:

```bash
curl -X POST http://localhost:9097/v1/crawl/channel   -H "Content-Type: application/json"   -d '{
    "channel": "examplechannel",
    "limit": 100,
    "stop_date": "2026-02-03"
  }'
```

The channel can also be supplied with `@`:

```json
{
  "channel": "@examplechannel",
  "limit": 100
}
```

The crawler normalizes the channel when constructing Telegram message URLs.

## Crawl Request

The request model contains the crawl parameters.

Example:

```json
{
  "channel": "examplechannel",
  "limit": 100,
  "stop_date": "2026-02-03"
}
```

### `channel`

Telegram channel handle.

Examples:

```text
examplechannel
```

or:

```text
@examplechannel
```

### `limit`

Maximum number of messages to crawl.

Example:

```json
{
  "limit": 100
}
```

### `stop_date`

Optional date used to stop crawling older messages.

Example:

```json
{
  "stop_date": "2026-02-03"
}
```

The crawler processes messages from newest to oldest. When a message older than the requested date is reached, crawling stops.

This prevents unnecessary traversal of older channel history.

## Crawl Response

Example:

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
      "created_at": "2026-02-03T12:30:00+00:00",
      "text": "Example Telegram message",
      "url": "https://t.me/examplechannel/12345",
      "is_forward": false,
      "has_media": false,
      "needs_processing": true,
      "sentiment_score": 0.4404,
      "engagement_count": 1250,
      "views": 1000,
      "forwards": 100,
      "reactions": 100,
      "message_length": 24,
      "mention_weight": 1.5,
      "hashtags": [
        "crypto"
      ],
      "cashtags": [
        "BTC"
      ],
      "contracts": [],
      "found_urls": [
        "https://example.com"
      ],
      "engagement_hash": "..."
    }
  ]
}
```

## Telegram Message Fields

Each crawled message is represented by the Telegram message model.

### `message_id`

A stable application-level identifier combining the channel handle and Telegram message ID.

Example:

```text
examplechannel_12345
```

### `community`

The Telegram channel handle.

Example:

```text
examplechannel
```

### `author`

The Telegram post author when Telegram provides one.

### `created_at`

The Telegram message creation timestamp.

### `text`

Normalized message text.

Whitespace is normalized before the message is processed.

### `url`

Direct Telegram message URL.

Example:

```text
https://t.me/examplechannel/12345
```

### `is_forward`

Indicates whether the message is a forwarded message.

### `has_media`

Indicates whether the message contains Telegram media.

### `needs_processing`

Indicates that the message is available for downstream processing.

### `sentiment_score`

VADER compound sentiment score.

The score ranges from:

```text
-1.0
```

to:

```text
1.0
```

### `engagement_count`

Combined engagement value calculated from:

```text
views + forwards + reactions + replies
```

### `views`

Telegram view count.

### `forwards`

Telegram forward count.

### `reactions`

Total reaction count.

### `message_length`

Length of the normalized message text.

### `mention_weight`

A calculated weight based on the configured channel weight and engagement.

The crawler currently calculates it using:

```text
channel_weight
+ views / 10000
+ forwards / 100
+ reactions / 200
+ replies / 50
```

The result is capped at:

```text
5.0
```

### `hashtags`

Hashtags extracted from Telegram message entities.

Example:

```json
[
  "bitcoin",
  "crypto"
]
```

### `cashtags`

Cashtags extracted from the message.

Example:

```json
[
  "BTC",
  "ETH"
]
```

### `contracts`

Contract-like addresses detected in the message.

### `found_urls`

URLs detected in the message.

### `engagement_hash`

A hash derived from:

```text
views
forwards
reactions
replies
```

It can be used to detect whether engagement has changed since a previous crawl.

## Text Normalization

Messages are normalized before processing.

The crawler:

- removes zero-width spaces
- collapses repeated whitespace
- strips leading and trailing whitespace

For example:

```text
"BTC    is
moving   higher"
```

becomes:

```text
"BTC is moving higher"
```

This makes message processing and comparison more stable.

## Sentiment

The crawler uses VADER to calculate sentiment.

Example:

```text
"BTC is breaking out and this looks extremely bullish"
```

produces a positive compound score.

A strongly negative message produces a negative score.

Neutral messages produce a score close to zero.

The raw `sentiment_score` is preserved in the response.

## Engagement

Telegram messages can expose several engagement metrics.

The crawler extracts:

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
views = 1000
forwards = 20
reactions = 50
replies = 10
```

Results in:

```text
engagement_count = 1080
```

## Engagement Hash

The crawler generates a Blake2b hash from the engagement values:

```text
views|forwards|reactions|replies
```

This allows downstream systems to quickly determine whether engagement has changed.

For example, if a message changes from:

```text
1000|20|50|10
```

to:

```text
1200|20|55|10
```

the engagement hash changes.

## Stop Date

`stop_date` is an optimization for historical crawling.

Example:

```json
{
  "channel": "examplechannel",
  "limit": 1000,
  "stop_date": "2026-02-03"
}
```

The crawler starts from recent messages and moves backwards.

Once it reaches a message whose date is older than the requested date, the crawler stops.

This is useful when you only want a specific historical window.

For example:

```text
latest message
      |
      v
2026-02-05
2026-02-04
2026-02-03
2026-02-02  <-- stop
```

The crawler does not continue unnecessarily through older messages.

## WebSocket Streaming

The WebSocket endpoint is intended for clients that want messages as they are discovered instead of waiting for the complete crawl.

Endpoint:

```text
WS /v1/ws/crawl/channel
```

The request is sent as JSON.

Example:

```json
{
  "channel": "examplechannel",
  "limit": 100,
  "stop_date": "2026-02-03"
}
```

Messages are streamed individually.

A typical stream contains item messages followed by a completion message.

Example item:

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

Completion:

```json
{
  "type": "done"
}
```

Error:

```json
{
  "type": "error",
  "detail": "Telegram client is not connected"
}
```

This design allows downstream applications to process messages immediately instead of waiting for the entire crawl.

## Why WebSockets

The normal POST endpoint behaves as a batch operation:

```text
request
   |
   v
crawl 100 messages
   |
   v
return 100 messages
```

The WebSocket endpoint behaves as a stream:

```text
request
   |
   v
message 1
   |
   v
message 2
   |
   v
message 3
   |
   v
...
   |
   v
done
```

This is useful for:

- real-time processing
- downstream sentiment pipelines
- token detection
- notifications
- event processing
- large crawls where waiting for the entire result is undesirable

## Concurrency

Crawls are protected by a concurrency semaphore.

Example:

```dotenv
MAX_CONCURRENT_CRAWLS=2
```

This allows two crawl operations to run simultaneously.

If both slots are occupied, new requests wait for an available slot.

The readiness endpoint exposes the current available slots.

Example:

```json
{
  "available_slots": 1,
  "max_concurrent_crawls": 2
}
```

## Error Handling

The API returns HTTP errors when the crawler cannot complete a request.

Example:

```json
{
  "detail": "Telegram client is not connected"
}
```

A crawl failure is returned as a server-side gateway error because the API itself is available but the external Telegram operation failed.

## Docker

TelegramCrawler is intended to run inside Docker.

Build:

```bash
docker build -t telegram-crawler .
```

Run:

```bash
docker run -d   --name telegram-crawler   -p 9097:9097   --env-file .env   telegram-crawler
```

Check the service:

```bash
curl http://localhost:9097/health
```

Check readiness:

```bash
curl http://localhost:9097/ready
```

## Docker Compose

Example:

```yaml
services:
  telegram-crawler:
    build: .
    container_name: telegram-crawler
    restart: unless-stopped
    ports:
      - "9097:9097"
    env_file:
      - .env
    volumes:
      - ./session:/app/session
```

The session directory should be persisted so the Telegram authentication session survives container recreation.

## Docker Health Check

A health check can use the service's health endpoint:

```dockerfile
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3   CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:9097/health')"
```

## API Usage From Python

Example HTTP client:

```python
import httpx


async def crawl_channel() -> dict:
    """Crawl a Telegram channel."""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:9097/v1/crawl/channel",
            json={
                "channel": "examplechannel",
                "limit": 100,
                "stop_date": "2026-02-03",
            },
        )
        response.raise_for_status()
        return response.json()
```

## WebSocket Usage From Python

Example:

```python
import json

import websockets


async def stream_channel() -> None:
    """Stream Telegram messages."""
    async with websockets.connect(
        "ws://localhost:9097/v1/ws/crawl/channel"
    ) as websocket:
        await websocket.send(
            json.dumps(
                {
                    "channel": "examplechannel",
                    "limit": 100,
                    "stop_date": "2026-02-03",
                }
            )
        )

        async for message in websocket:
            data = json.loads(message)

            if data["type"] == "item":
                print(data["data"])
            elif data["type"] == "done":
                break
            elif data["type"] == "error":
                raise RuntimeError(data["detail"])
```

## Why Only One Crawl Endpoint

The API intentionally exposes one crawl operation:

```text
POST /v1/crawl/channel
```

Telegram channel crawling is the core operation.

There is no need to create separate endpoints for:

- recent messages
- historical messages
- messages by date
- messages by ID

Those behaviors can be represented through request parameters such as `limit` and `stop_date`.

This keeps the HTTP API small and easier to maintain.

## Should More Channels Be Added?

The current API accepts one channel per crawl request.

That is preferable for the current service design.

Multiple channels can already be handled by the client by making multiple crawl requests.

For example:

```text
channel A -> /v1/crawl/channel
channel B -> /v1/crawl/channel
channel C -> /v1/crawl/channel
```

Adding a bulk endpoint such as:

```text
POST /v1/crawl/channels
```

would only be worthwhile if the service itself needs to coordinate multiple channels in one operation.

A bulk endpoint would introduce additional concerns:

- per-channel errors
- concurrency scheduling
- response aggregation
- partial failures
- ordering
- larger response sizes
- WebSocket multiplexing

For a small crawler microservice, keeping one-channel-per-operation is the simpler design.

## Development

Run the application:

```bash
python -m src.main
```

Run with a custom port:

```bash
PORT=9098 python -m src.main
```

Run with a custom concurrency limit:

```bash
MAX_CONCURRENT_CRAWLS=4 python -m src.main
```

## API Documentation

FastAPI automatically provides OpenAPI documentation.

Swagger UI:

```text
http://localhost:9097/docs
```

ReDoc:

```text
http://localhost:9097/redoc
```

OpenAPI schema:

```text
http://localhost:9097/openapi.json
```

## Design Principles

TelegramCrawler follows a small set of design principles.

### Keep the API Small

The service exposes only the operations needed to crawl Telegram content.

### Keep Telegram Logic in the Crawler

FastAPI should not contain Telethon-specific extraction logic.

### Keep the Crawler Reusable

The crawler can be used by HTTP and WebSocket handlers without duplicating crawling code.

### Prefer Streaming for Large or Real-Time Workflows

WebSockets allow clients to consume messages as soon as they are discovered.

### Keep REST for Simple Integrations

The POST endpoint remains useful for scripts and clients that want one complete response.

### Keep Authentication State Persistent

The Telethon session should be stored outside the disposable application process.

## Future Improvements

Possible future improvements include:

- channel bulk crawling
- message ID ranges
- date ranges with both start and end dates
- media metadata extraction
- reply/thread extraction
- forwarded-message metadata
- richer reaction information
- configurable sentiment engines
- crawl statistics
- retry handling for transient Telegram failures
- more granular WebSocket events
- optional persistent storage

These should only be added when they solve an actual requirement. The current service is intentionally narrow.

## Security

Do not expose the Telegram API credentials publicly.

Do not commit:

```text
.env
```

or:

```text
*.session
```

to the repository.

The Telegram session effectively represents an authenticated Telegram client and should be treated as sensitive.

When deploying the API publicly, place it behind appropriate network controls and authentication if the service should not be publicly accessible.

## License
- MIT
