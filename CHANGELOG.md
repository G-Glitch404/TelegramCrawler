# Changelog

All notable changes to TelegramCrawler are documented in this file.

## [Unreleased]

### Added

- Added Telegram channel crawling through Telethon
- Added `GET /health` endpoint
- Added `GET /ready` endpoint
- Added `POST /v1/crawl/channel` endpoint
- Added `WS /v1/ws/crawl/channel` for streaming Telegram messages
- Added Pydantic request and response models
- Added configurable crawl concurrency
- Added Telegram client connection state checking
- Added `stop_date` support for historical crawling
- Added VADER sentiment analysis
- Added message engagement extraction
- Added message view, forward, reaction, and reply counts
- Added message engagement hashing
- Added hashtag extraction
- Added cashtag extraction
- Added contract address extraction
- Added URL extraction
- Added Telegram message URL generation
- Added message text normalization
- Added media detection
- Added forwarded-message detection
- Added channel weighting and mention-weight calculation

### Changed

- Separated Telegram crawling logic from the FastAPI API layer
- Centralized Telegram client handling inside `TelegramCrawler`
- Added shared crawler functionality for REST and WebSocket clients
- Changed crawling to process messages from newest to oldest
- Added date-based early termination to avoid unnecessarily processing older messages
- Changed the API to use a single channel crawl operation rather than separate endpoints for different crawl modes
- Added readiness reporting for Telegram connection state and available crawl slots
- Configured the application to run on port `9097` by default
- Added environment-based configuration for host, port, Telegram credentials, and crawl concurrency

### Documentation

- Added project architecture documentation
- Added API endpoint documentation
- Added REST request and response examples
- Added WebSocket usage examples
- Added Telegram message field documentation
- Added `stop_date` documentation
- Added environment variable documentation
- Added Docker usage documentation
- Added authentication and Telegram session documentation
- Added concurrency documentation
- Added security guidance for Telegram credentials and session files

### Design

- Kept the service intentionally small and focused around Telegram channel crawling
- Kept channel crawling as a single-channel operation per request
- Added WebSocket support for clients that need incremental message delivery
- Kept the REST endpoint for clients that need a complete crawl response
- Designed the crawler to be reusable by both HTTP and WebSocket interfaces

### Security

- Added support for environment-based Telegram API credentials
- Documented protection of Telethon session files
- Documented `.env` and session files as sensitive data
- Added guidance for protecting the API when exposed outside a trusted network
