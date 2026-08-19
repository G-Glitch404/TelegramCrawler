import hashlib
import os
import re
import datetime as dt

from pathlib import Path
from typing import Any, Optional, AsyncGenerator, Sequence

from telethon.client import TelegramClient
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

from src.items import TelegramMessage


SPACE_RE = re.compile(r"\s+")
CASHTAG_RE = re.compile(r"\$([A-Za-z][A-Za-z0-9_]{0,31})")
URL_RE = re.compile(r"https?://[^\s<>\"]+")

TELEGRAM_API_ID = int(os.getenv("TELEGRAM_APP_ID", "0"))
TELEGRAM_API_HASH = os.getenv("TELEGRAM_API_HASH", "")
TELEGRAM_SESSION = os.getenv(
    "TELEGRAM_SESSION",
    str(Path("/session") / "telegram_crawler.session"),
)

if not TELEGRAM_API_ID:
    raise RuntimeError("TELEGRAM_APP_ID is not configured")

if not TELEGRAM_API_HASH:
    raise RuntimeError("TELEGRAM_API_HASH is not configured")


_client = TelegramClient(
    TELEGRAM_SESSION,
    TELEGRAM_API_ID,
    TELEGRAM_API_HASH,
)


class TelegramCrawler:
    def __init__(self) -> None:
        self.entities: dict[str, Any] = {}
        self.sentiment_analyzer = SentimentIntensityAnalyzer()

    @staticmethod
    async def connect() -> None:
        """ connect to telegram using the configured session """
        if not _client.is_connected():
            await _client.connect()

        if not await _client.is_user_authorized():
            raise RuntimeError("telegram session is not authorized")

    @staticmethod
    async def disconnect() -> None:
        """ disconnect the telegram client """
        if _client.is_connected():
            _client.disconnect()

    @staticmethod
    def _normalize_text(text: Optional[str]) -> str:
        """ normalize telegram text for stable processing """
        return SPACE_RE.sub(
            " ",
            (text or "").replace("\u200b", " "),
        ).strip()

    @staticmethod
    def _extract_cashtag(text: str) -> str:
        """ extract the most likely symbol from a telegram message """
        match = CASHTAG_RE.search(text)
        return match.group(1).upper() if match else ""

    async def build_entities(self, channels: Sequence[str]) -> None:
        """ load telegram channels into cached api entities """
        await self.connect()
        for channel in channels:
            if channel not in self.entities:
                self.entities[channel] = await _client.get_input_entity(channel)

    async def fetch_channel(
        self,
        channel_handle: str,
        limit: int = 100,
        stop_date: Optional[dt.datetime] = None,
    ) -> AsyncGenerator[TelegramMessage, None]:
        """ fetch and convert telegram channel messages into normalized items """
        await self.build_entities([channel_handle])

        entity = self.entities[channel_handle]
        async for message in _client.iter_messages(
            entity,
            reverse=False,
            limit=limit,
        ):
            message_date = getattr(message, "date", None)
            if stop_date is not None:
                if not isinstance(message_date, dt.datetime): break
                if message_date.date() < stop_date.date(): break

            text: str = self._normalize_text(getattr(message, "message", None))
            if not text: continue

            sentiment_score = self.sentiment_analyzer.polarity_scores(text)["compound"]

            reactions: int = 0
            if message.reactions and getattr(message.reactions, "results", None):
                reactions = sum(
                    int(result.count or 0)
                    for result in message.reactions.results
                )

            replies: int = 0
            if message.replies:
                replies: int = int(message.replies.replies or 0)

            hashtags: set[str] = set()
            entities: list = getattr(message, "entities", None) or []
            for entity_item in entities:
                if entity_item.__class__.__name__ != "MessageEntityHashtag": continue

                offset: int = int(entity_item.offset)
                length: int = int(entity_item.length)

                hashtags.add(
                    text[offset:offset + length].lstrip("#")
                )

            cashtags: set[str] = {
                match.group(1).upper()
                for match in CASHTAG_RE.finditer(text)
            }

            found_urls: set[str] = {
                match.group(0)
                for match in URL_RE.finditer(text)
            }

            views: int = int(message.views or 0)
            forwards: int = int(message.forwards or 0)

            engagement_count = (
                views +
                forwards +
                reactions +
                replies
            )

            mention_weight = min(
                4.0,
                views / 10_000 +
                forwards / 100 +
                reactions / 200 +
                replies / 50,
            )

            yield TelegramMessage(
                message_id=message.id,
                community=channel_handle,
                unique_id=f"{channel_handle}_{message.id}",
                author=getattr(message, "post_author", None),
                created_at=message.date,
                text=text,
                message_length=len(text),
                words_count=len([word for word in text.split() if len(word) > 3]),
                url=f"https://t.me/{channel_handle.lstrip('@')}/{message.id}",
                is_forward=bool(message.fwd_from),
                has_media=message.media is not None,
                sentiment_score=sentiment_score,
                engagement_count=engagement_count,
                views=views,
                forwards=forwards,
                reactions=reactions,
                replies=replies,
                mention_weight=mention_weight,
                hashtags=hashtags,
                cashtags=cashtags,
                found_urls=found_urls,
                engagement_hash=hashlib.blake2b(
                    f"{views}|{forwards}|{reactions}|{replies}".encode(),
                    digest_size=16,
                ).hexdigest()
            )

    async def crawl_channel(
        self,
        channel_handle: str,
        limit: int = 100,
        stop_date: Optional[dt.datetime] = None,
    ) -> list[TelegramMessage]:
        """ crawl a telegram channel and return its messages """
        return [
            message
            async for message in self.fetch_channel(
                channel_handle=channel_handle,
                limit=limit,
                stop_date=stop_date,
            )
        ]


if __name__ == '__main__':
    _client.start()
