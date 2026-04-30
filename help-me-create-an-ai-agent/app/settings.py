from __future__ import annotations

import os
from dataclasses import dataclass

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass


def _split_csv(value: str) -> tuple[str, ...]:
    return tuple(item.strip() for item in value.split(",") if item.strip())


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int, minimum: int, maximum: int) -> int:
    value = os.getenv(name)
    if not value:
        return default
    try:
        parsed = int(value)
    except ValueError:
        return default
    return max(minimum, min(maximum, parsed))


@dataclass(frozen=True)
class Settings:
    discord_bot_token: str
    discord_user_id: str
    topics: tuple[str, ...]
    news_language: str
    news_country: str
    news_ceid: str
    news_lookback_days: int
    news_items_per_topic: int
    gemini_model: str
    digest_timezone: str
    agent_run_token: str | None
    dry_run: bool
    discord_api_base: str


def load_settings() -> Settings:
    topics = _split_csv(
        os.getenv(
            "NEWS_TOPICS",
            "artificial intelligence,google cloud,cybersecurity",
        )
    )

    return Settings(
        discord_bot_token=os.getenv("DISCORD_BOT_TOKEN", "").strip(),
        discord_user_id=os.getenv("DISCORD_USER_ID", "").strip(),
        topics=topics,
        news_language=os.getenv("NEWS_LANGUAGE", "en-US").strip(),
        news_country=os.getenv("NEWS_COUNTRY", "US").strip(),
        news_ceid=os.getenv("NEWS_CEID", "US:en").strip(),
        news_lookback_days=_env_int("NEWS_LOOKBACK_DAYS", 1, 1, 14),
        news_items_per_topic=_env_int("NEWS_ITEMS_PER_TOPIC", 5, 1, 10),
        gemini_model=os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip(),
        digest_timezone=os.getenv("DIGEST_TIMEZONE", "UTC").strip(),
        agent_run_token=os.getenv("AGENT_RUN_TOKEN") or None,
        dry_run=_env_bool("DRY_RUN", False),
        discord_api_base=os.getenv(
            "DISCORD_API_BASE", "https://discord.com/api/v10"
        ).rstrip("/"),
    )

