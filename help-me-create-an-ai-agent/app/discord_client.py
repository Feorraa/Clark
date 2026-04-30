from __future__ import annotations

import asyncio
from dataclasses import dataclass

import httpx


DISCORD_MESSAGE_LIMIT = 2000
SAFE_CHUNK_LIMIT = 1850


def split_discord_message(
    content: str,
    *,
    limit: int = SAFE_CHUNK_LIMIT,
) -> list[str]:
    content = content.replace("\r\n", "\n").replace("\r", "\n").strip()
    if not content:
        return []

    chunks: list[str] = []
    current = ""

    for line in content.split("\n"):
        candidate = line if not current else f"{current}\n{line}"
        if len(candidate) <= limit:
            current = candidate
            continue

        if current:
            chunks.append(current)
            current = ""

        remaining = line
        while len(remaining) > limit:
            cut = remaining.rfind(" ", 0, limit)
            if cut < int(limit * 0.6):
                cut = limit
            chunks.append(remaining[:cut].rstrip())
            remaining = remaining[cut:].lstrip()
        current = remaining

    if current:
        chunks.append(current)

    return chunks


@dataclass
class DiscordClient:
    bot_token: str
    api_base: str

    async def _request(
        self,
        client: httpx.AsyncClient,
        method: str,
        path: str,
        *,
        json: dict | None = None,
    ) -> dict:
        url = f"{self.api_base}{path}"
        for _ in range(5):
            response = await client.request(method, url, json=json)
            if response.status_code == 429:
                retry_after = response.json().get("retry_after", 1)
                await asyncio.sleep(float(retry_after) + 0.25)
                continue
            response.raise_for_status()
            if not response.content:
                return {}
            return response.json()
        response.raise_for_status()
        return {}

    async def send_dm(self, user_id: str, content: str) -> int:
        if not self.bot_token:
            raise ValueError("DISCORD_BOT_TOKEN is required when sending messages")
        if not user_id:
            raise ValueError("DISCORD_USER_ID is required when sending messages")

        headers = {
            "Authorization": f"Bot {self.bot_token}",
            "Content-Type": "application/json",
            "User-Agent": "daily-news-discord-agent/0.1",
        }
        timeout = httpx.Timeout(20.0, connect=10.0)

        async with httpx.AsyncClient(headers=headers, timeout=timeout) as client:
            channel = await self._request(
                client,
                "POST",
                "/users/@me/channels",
                json={"recipient_id": user_id},
            )
            channel_id = channel["id"]

            sent = 0
            for chunk in split_discord_message(content):
                if len(chunk) > DISCORD_MESSAGE_LIMIT:
                    raise ValueError("Message chunk exceeds Discord message limit")
                await self._request(
                    client,
                    "POST",
                    f"/channels/{channel_id}/messages",
                    json={"content": chunk},
                )
                sent += 1

            return sent

