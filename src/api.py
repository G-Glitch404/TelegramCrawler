import asyncio
import os
import time

from typing import Any
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi import WebSocket, WebSocketDisconnect

from src.crawler import TelegramCrawler
from src.items import (
    TelegramMessage,
    CrawlChannelRequest,
    CrawlChannelResponse,
)


MAX_CONCURRENT_CRAWLS = int(os.getenv("MAX_CONCURRENT_CRAWLS", "4"))

crawl_gate = asyncio.Semaphore(MAX_CONCURRENT_CRAWLS)
_crawler = TelegramCrawler()


@asynccontextmanager
async def lifespan(_: FastAPI):
    """ manage the telegram client lifecycle """
    await _crawler.connect()
    try: yield
    finally: await _crawler.disconnect()


app = FastAPI(
    title="TelegramCrawler",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)


@app.get("/health")
async def health() -> dict[str, Any]:
    """ return service liveness information """
    return {
        "status": "healthy",
        "service": "telegram-_crawler",
        "version": app.version,
    }


@app.get("/ready")
async def ready() -> dict[str, Any]:
    """ return service readiness information """
    connected: bool = True
    failure: str = 'no issues'
    try: await _crawler.connect()
    except Exception as e:
        connected: bool = False
        failure = str(e)

    return {
        "status": "ready" if connected else "not_ready",
        "failure": failure,
        "telegram_connected": connected,
        "available_slots": crawl_gate._value,
        "max_concurrent_crawls": MAX_CONCURRENT_CRAWLS,
    }


@app.post(
    "/v1/crawl/channel",
    response_model=CrawlChannelResponse,
)
async def crawl_channel(
    req: CrawlChannelRequest,
) -> CrawlChannelResponse:
    """ crawl a telegram channel """
    started = time.perf_counter()

    async with crawl_gate:
        try:
            messages: list[TelegramMessage] = await _crawler.crawl_channel(
                channel_handle=req.channel,
                limit=req.limit,
                stop_date=req.stop_date,
            )
        except Exception as exc:
            raise HTTPException(
                status_code=502,
                detail=str(exc),
            ) from exc

    elapsed_ms: int = int(
        (time.perf_counter() - started) * 1000
    )

    return CrawlChannelResponse(
        channel=req.channel,
        limit=req.limit,
        count=len(messages),
        elapsed_ms=elapsed_ms,
        messages=messages,
    )


@app.websocket("/v1/ws/crawl/channel")
async def ws_crawl_channel(websocket: WebSocket) -> None:
    """ stream telegram channel messages over websocket """
    await websocket.accept()

    try:
        payload: Any = await websocket.receive_json()
        req: CrawlChannelRequest = CrawlChannelRequest.model_validate(payload)

        async with crawl_gate:
            async for message in _crawler.fetch_channel(
                channel_handle=req.channel,
                limit=req.limit,
                stop_date=req.stop_date,
            ):
                await websocket.send_json({
                    "type": "item",
                    "data": message.model_dump(mode="json"),
                })

        await websocket.send_json({
            "type": "done",
        })

    except WebSocketDisconnect: return
    except ValueError as exc: await websocket.send_json({"type": "error", "detail": str(exc)})
    except RuntimeError as exc: await websocket.send_json({"type": "error", "detail": str(exc)})
    finally:
        if websocket.client_state.value == 1:
            await websocket.close()
