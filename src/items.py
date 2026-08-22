import datetime as dt

from typing import Optional

from pydantic import BaseModel, Field, field_validator


class CrawlChannelRequest(BaseModel):
    channel: str = Field(min_length=1, max_length=255)
    limit: int = Field(default=100, ge=1, le=10_000)
    stop_date: Optional[dt.datetime] = None

    @field_validator("channel")
    @classmethod
    def normalize_channel(cls, value: str) -> str:
        value: str = value.strip()

        if value.startswith("https://t.me/"):
            value: str = value.removeprefix("https://t.me/").split("/", 1)[0]

        if value.startswith("@"):
            value: str = value[1:]

        if not value:
            raise ValueError("invalid telegram channel")

        return value


class TelegramMessage(BaseModel):
    message_id: int
    community: str
    unique_id: str
    author: Optional[str] = None
    created_at: dt.datetime
    text: str
    message_length: int
    words_count: int
    url: str
    is_forward: bool
    has_media: bool
    sentiment_score: float
    engagement_count: int
    views: int
    forwards: int
    reactions: int
    replies: int
    mention_weight: float
    hashtags: set[str]
    cashtags: set[str]
    found_urls: set[str]
    engagement_hash: str


class CrawlChannelResponse(BaseModel):
    channel: str
    limit: int
    count: int
    elapsed_ms: int
    messages: list[TelegramMessage]
