from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime

from app.digest import render_fallback_digest, render_prompt
from app.news import Article

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SummaryResult:
    text: str
    used_ai: bool
    error: str | None = None


class GeminiSummarizer:
    def __init__(self, model: str) -> None:
        self.model = model

    async def summarize(
        self,
        digest_date: datetime,
        articles_by_topic: dict[str, list[Article]],
    ) -> SummaryResult:
        prompt = render_prompt(digest_date, articles_by_topic)

        try:
            from google import genai
            from google.genai.types import HttpOptions

            client = genai.Client(http_options=HttpOptions(api_version="v1"))
            response = await asyncio.to_thread(
                client.models.generate_content,
                model=self.model,
                contents=prompt,
            )
            text = (getattr(response, "text", "") or "").strip()
            if text:
                return SummaryResult(text=text, used_ai=True)
            raise RuntimeError("Gemini returned an empty response")
        except Exception as exc:  # noqa: BLE001
            logger.exception("Gemini summarization failed")
            return SummaryResult(
                text=render_fallback_digest(digest_date, articles_by_topic),
                used_ai=False,
                error=f"{type(exc).__name__}: {exc}",
            )

