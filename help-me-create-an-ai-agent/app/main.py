from __future__ import annotations

import hmac
import logging
from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import FastAPI, Header, HTTPException, Query
from fastapi.responses import PlainTextResponse

from app.ai import GeminiSummarizer
from app.discord_client import DiscordClient
from app.news import fetch_all_topics
from app.settings import Settings, load_settings


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Daily News Discord Agent", version="0.1.0")


def _digest_now(settings: Settings) -> datetime:
    try:
        return datetime.now(ZoneInfo(settings.digest_timezone))
    except ZoneInfoNotFoundError:
        logger.warning("Unknown DIGEST_TIMEZONE=%s; falling back to UTC", settings.digest_timezone)
        return datetime.now(ZoneInfo("UTC"))


def _verify_agent_token(
    settings: Settings,
    authorization: str | None,
    x_agent_token: str | None,
) -> None:
    if not settings.agent_run_token:
        return

    supplied = x_agent_token or ""
    if not supplied and authorization:
        scheme, _, token = authorization.partition(" ")
        if scheme.lower() == "bearer":
            supplied = token

    if not hmac.compare_digest(supplied, settings.agent_run_token):
        raise HTTPException(status_code=401, detail="Invalid agent run token")


@app.get("/", response_class=PlainTextResponse)
async def root() -> str:
    return "Daily News Discord Agent is running. POST /run to generate a brief.\n"


@app.get("/health")
async def health() -> dict[str, bool]:
    return {"ok": True}


@app.post("/run")
async def run_digest(
    send: bool = Query(True, description="Set false to preview without sending to Discord."),
    authorization: str | None = Header(None),
    x_agent_token: str | None = Header(None),
) -> dict:
    settings = load_settings()
    _verify_agent_token(settings, authorization, x_agent_token)

    if not settings.topics:
        raise HTTPException(status_code=400, detail="NEWS_TOPICS must contain at least one topic")

    digest_date = _digest_now(settings)
    articles_by_topic = await fetch_all_topics(
        settings.topics,
        lookback_days=settings.news_lookback_days,
        language=settings.news_language,
        country=settings.news_country,
        ceid=settings.news_ceid,
        limit=settings.news_items_per_topic,
    )

    summary = await GeminiSummarizer(settings.gemini_model).summarize(
        digest_date,
        articles_by_topic,
    )

    should_send = send and not settings.dry_run
    message_count = 0
    if should_send:
        message_count = await DiscordClient(
            settings.discord_bot_token,
            settings.discord_api_base,
        ).send_dm(settings.discord_user_id, summary.text)

    article_count = sum(len(articles) for articles in articles_by_topic.values())
    return {
        "sent": should_send,
        "discord_messages": message_count,
        "used_ai": summary.used_ai,
        "ai_error": summary.error,
        "topics": settings.topics,
        "article_count": article_count,
        "digest": None if should_send else summary.text,
    }

