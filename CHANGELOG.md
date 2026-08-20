# Changelog

All notable changes to **TelegramCrawler** are documented in this file.

The project follows an **Unreleased-first** changelog style: changes are recorded here as they land and can later be grouped into a versioned release.

---

## [Unreleased]

### ✨ Added

#### Telegram Crawling

- Added authenticated Telegram channel crawling through **Telethon**.
- Added a shared `TelegramCrawler` implementation that can be consumed by both HTTP and WebSocket interfaces.
- Added newest-to-oldest message traversal for efficient historical crawling.
- Added `stop_date` support for bounded historical crawls, with early termination once messages fall outside the requested date boundary.
- Added configurable crawl concurrency through `MAX_CONCURRENT_CRAWLS`.
- Added Telegram connection-state validation before crawl operations.

#### HTTP API

- Added `GET /health` for lightweight process liveness checks.
- Added `GET /ready` for Telegram connectivity and crawl-capacity readiness checks.
- Added `POST /v1/crawl/channel` for complete, request/response channel crawls.
- Added `WS /v1/ws/crawl/channel` for incremental message streaming.
- Added Pydantic request and response models for explicit API contracts and validation.
- Added FastAPI-generated OpenAPI documentation through `/docs`, `/redoc`, and `/openapi.json`.

#### Message Processing

- Added message text normalization, including zero-width-space removal, whitespace collapsing, and trimming.
- Added Telegram message URL generation.
- Added media detection.
- Added forwarded-message detection.
- Added author extraction where Telegram provides author information.
- Added hashtag extraction.
- Added cashtag extraction.
- Added contract-like address extraction.
- Added URL extraction.
- Added VADER sentiment analysis with a normalized compound score.
- Added view, forward, reaction, and reply extraction.
- Added aggregate `engagement_count` calculation.
- Added deterministic engagement hashing to make engagement changes easy to detect downstream.
- Added channel-aware `mention_weight` calculation with an upper bound.

#### Deployment & Operations

- Added Docker packaging for the crawler service.
- Added Docker Compose deployment configuration.
- Added persistent Docker storage for the Telethon session.
- Added container health checks against `/health`.
- Added production environment support through `.env/.env.prod`.
- Added development/test environment separation through `.env/.env.dev` and `.env/.env.test`.
- Added a documented `uv`-based session-generation workflow so a new installation can authenticate Telethon before starting the API.

#### Testing

- Added integration coverage for `/ready`.
- Added integration coverage for `POST /v1/crawl/channel`.
- Added response-contract assertions for crawled message fields.
- Added environment-driven test configuration including `CRAWLER_BASE_URL`, `TEST_TELEGRAM_CHANNEL`, `TEST_CRAWL_LIMIT`, `TEST_STOP_DATE`, and `TEST_REQUEST_TIMEOUT`.
- Added support for running pytest through `uv` with an explicit environment file.

---

### 🔄 Changed

#### Architecture

- Separated **Telegram-specific crawling and message processing** from the FastAPI transport layer.
- Centralized Telegram client lifecycle and connection state inside the crawler layer.
- Reused the same crawl pipeline for REST and WebSocket consumers instead of duplicating crawling logic.
- Kept the public API intentionally narrow: one primary crawl operation per request rather than separate endpoints for recent, historical, date-based, or ID-based crawling.
- Preserved a single-channel-per-request model so concurrency remains centrally controlled by the service.

#### Crawling Behaviour

- Changed crawl traversal to move from newer messages toward older messages.
- Added date-based early termination to avoid unnecessary traversal of older channel history.
- Made `stop_date` an optimization boundary rather than a separate crawl mode.
- Added centralized semaphore-based concurrency control so requests wait for available crawl capacity instead of creating unbounded Telegram work.

#### Configuration

- Moved runtime configuration toward environment-driven deployment.
- Standardized the default API port to `9097`.
- Added configurable host, port, Telegram credentials, session path, concurrency, and timeout settings.
- Distinguished **Compose interpolation variables** from container `env_file` values in deployment documentation.
- Standardized production startup around:

  ```bash
  docker compose --env-file .env/.env.prod up -d --build
  ```

  The placement of `--env-file` before `up` is intentional and required for Compose-level variable interpolation.

#### Authentication State

- Made the Telethon session a deliberate piece of persistent application state rather than disposable container state.
- Documented the Docker session mount so container recreation does not unnecessarily invalidate the authenticated Telegram session.
- Documented that the session can either be supplied directly or generated with `crawler.py` using `uv` and the appropriate environment file.

---

### 🐛 Fixed / Hardened

- Hardened Telegram message model validation around Telegram's numeric message identifiers.
- Improved handling of API failures so a Telegram/message-processing failure is surfaced as an explicit server-side crawl error instead of being mistaken for a client-side HTTP problem.
- Added readiness checks that distinguish a reachable API from a fully usable Telegram crawler.
- Added explicit test assertions for message structure, response counts, timing metadata, and crawl limits.
- Added cleanup of HTTP test clients after integration-test execution.
- Improved environment loading guidance for PyCharm, pytest, `uv`, and Docker so tests and local development do not accidentally use the wrong configuration.

---

### 🧪 Testing & Developer Experience

- Added a dedicated pytest configuration for project-level test execution.
- Added verbose pytest usage for debugging integration tests:

  ```bash
  uv run --env-file .env/.env.test pytest -vv -s
  ```

- Added focused test execution examples:

  ```bash
  uv run --env-file .env/.env.test pytest tests/test_post_endpoint.py -vv -s
  ```

- Documented the distinction between PyCharm's pytest runner and the raw pytest terminal output.
- Added environment-specific development, test, and production workflows instead of relying on one shared `.env` file.

---

### 📚 Documentation

- Reworked the README into a complete operator/developer guide.
- Added a project architecture overview and component responsibilities.
- Added environment variable reference and examples.
- Added Telegram API credential setup guidance.
- Added Telethon session creation and authentication workflow.
- Added Docker and Docker Compose deployment instructions.
- Added Docker lifecycle commands for start, stop, restart, rebuild, logs, and health checks.
- Added REST endpoint documentation with request/response examples.
- Added WebSocket protocol documentation with `item`, `done`, and `error` events.
- Added complete Telegram message-field documentation.
- Added explanations for text normalization, sentiment, engagement, engagement hashes, entity extraction, and mention weighting.
- Added production deployment checklist.
- Added troubleshooting guidance for readiness failures, missing sessions, Compose environment warnings, crawl `502` errors, and port conflicts.
- Added security guidance for Telegram credentials, `.env` files, and Telethon session files.

---

### 🐳 Docker & Production

- Added a production-oriented Docker image based on Python 3.12 slim.
- Added `uv` inside the image for locked dependency installation and reproducible startup.
- Added `tini` as the container entrypoint for clean signal handling.
- Added a persistent `telegram_session` Docker volume mounted at `/app/session`.
- Added an external `crawlers-network` integration for connecting the crawler to other services.
- Added DNS configuration for containerized Telegram connectivity.
- Added Docker health checks using `/health`.
- Added production startup documentation emphasizing the correct Compose invocation:

  ```bash
  docker compose --env-file .env/.env.prod up -d --build
  ```

- Added operational commands for inspecting the running service:

  ```bash
  docker compose ps
  docker compose logs -f telegram-crawler
  docker compose restart telegram-crawler
  docker compose down
  ```

---

### 🔐 Security

- Standardized Telegram API credentials as environment-provided secrets.
- Documented `TELEGRAM_APP_ID` and `TELEGRAM_API_HASH` as sensitive configuration.
- Documented `*.session` and `*.session-journal` as sensitive authentication state.
- Added guidance not to commit `.env/.env.prod` or Telethon session files.
- Added guidance not to copy session files into public container images or expose them through logs and issue trackers.
- Documented the need for network controls, authentication, or a reverse proxy when exposing the API outside a trusted network.

---

### 🎨 Design & API Philosophy

- Kept the crawler intentionally small and focused on one core job: **turn Telegram channel history into normalized, structured, analysis-ready message data**.
- Kept REST semantics simple for consumers that want one complete result.
- Added WebSockets as the streaming path for consumers that need immediate per-message processing.
- Kept transport concerns in the API layer and Telegram concerns in the crawler layer.
- Treated persistent Telegram authentication as infrastructure state rather than business data.
- Favoured configurable behaviour through environment variables over hard-coded deployment values.
- Favoured explicit contracts and validation over loosely shaped Telegram payloads.

---

### 📦 Current Runtime Surface

| Interface | Endpoint                  | Purpose                                         |
|-----------|---------------------------|-------------------------------------------------|
| HTTP      | `GET /health`             | Process liveness                                |
| HTTP      | `GET /ready`              | Telegram readiness and available crawl capacity |
| HTTP      | `POST /v1/crawl/channel`  | Complete channel crawl                          |
| WebSocket | `WS /v1/ws/crawl/channel` | Incremental crawl streaming                     |
| OpenAPI   | `/docs`                   | Interactive Swagger UI                          |
| OpenAPI   | `/redoc`                  | ReDoc API documentation                         |
| OpenAPI   | `/openapi.json`           | Machine-readable API schema                     |

---
