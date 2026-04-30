from __future__ import annotations

from datetime import datetime

from app.news import Article


def _article_date(article: Article) -> str:
    if not article.published_at:
        return "unknown"
    return article.published_at.strftime("%Y-%m-%d %H:%M UTC")


def render_prompt(
    digest_date: datetime,
    articles_by_topic: dict[str, list[Article]],
) -> str:
    lines = [
        "You are a concise news analyst writing one Discord DM for one user.",
        "Use only the supplied RSS article metadata. Do not invent facts.",
        "Prefer clear, useful analysis over hype. Flag uncertainty when the metadata is thin.",
        "Format in Discord-friendly Markdown.",
        "Keep the whole brief compact. Aim for 1-3 bullets per topic and a short watchlist.",
        f"Digest date: {digest_date.strftime('%Y-%m-%d')}",
        "",
        "Article metadata:",
    ]

    for topic, articles in articles_by_topic.items():
        lines.append(f"\nTopic: {topic}")
        if not articles:
            lines.append("No fresh RSS items found.")
            continue
        for index, article in enumerate(articles, start=1):
            summary = article.summary[:500]
            lines.extend(
                [
                    f"[{index}] Title: {article.title}",
                    f"Source: {article.source}",
                    f"Published: {_article_date(article)}",
                    f"Snippet: {summary}",
                    f"URL: {article.url}",
                ]
            )

    lines.extend(
        [
            "",
            "Output shape:",
            f"**Daily News Brief - {digest_date.strftime('%b %d, %Y')}**",
            "",
            "**Topic name**",
            "- **Headline-level takeaway.** One sentence on what happened, then one sentence on why it matters. Source: <URL>",
            "",
            "**Watchlist**",
            "- One or two things to watch next.",
        ]
    )
    return "\n".join(lines)


def render_fallback_digest(
    digest_date: datetime,
    articles_by_topic: dict[str, list[Article]],
) -> str:
    lines = [f"**Daily News Brief - {digest_date.strftime('%b %d, %Y')}**", ""]

    for topic, articles in articles_by_topic.items():
        lines.append(f"**{topic}**")
        if not articles:
            lines.append("- No fresh RSS items found.")
            lines.append("")
            continue

        for article in articles[:5]:
            lines.append(f"- **{article.title}**")
            lines.append(f"  Source: {article.source} | {article.url}")
        lines.append("")

    lines.append(
        "_Gemini summary was unavailable, so this fallback brief lists the top RSS items._"
    )
    return "\n".join(lines).strip()

