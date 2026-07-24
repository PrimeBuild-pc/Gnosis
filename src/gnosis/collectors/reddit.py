from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import UTC, datetime

import asyncpraw

from ..config import Settings, SourceConfig
from ..types import CollectedMessage

Emit = Callable[[CollectedMessage], int | None]


async def run(settings: Settings, sources: list[SourceConfig], emit: Emit) -> None:
    if not settings.reddit_client_id or not settings.reddit_client_secret:
        raise ValueError("Credenziali Reddit mancanti")
    reddit = asyncpraw.Reddit(
        client_id=settings.reddit_client_id,
        client_secret=settings.reddit_client_secret,
        user_agent=settings.reddit_user_agent,
    )
    try:
        while True:
            for source in sources:
                subreddit = await reddit.subreddit(source.external_id)
                async for post in subreddit.new(limit=100):
                    text = f"{post.title}\n\n{post.selftext}".strip()
                    if text:
                        emit(
                            CollectedMessage(
                                platform="reddit",
                                source_external_id=source.external_id,
                                external_id=post.name,
                                author=str(post.author or "[deleted]"),
                                sent_at=datetime.fromtimestamp(post.created_utc, UTC),
                                text=text,
                                url=f"https://www.reddit.com{post.permalink}",
                                metadata={"score": post.score, "type": "submission"},
                            )
                        )
                async for comment in subreddit.comments(limit=100):
                    if comment.body and comment.body not in {"[deleted]", "[removed]"}:
                        emit(
                            CollectedMessage(
                                platform="reddit",
                                source_external_id=source.external_id,
                                external_id=comment.name,
                                author=str(comment.author or "[deleted]"),
                                sent_at=datetime.fromtimestamp(comment.created_utc, UTC),
                                text=comment.body,
                                url=f"https://www.reddit.com{comment.permalink}",
                                thread_id=comment.link_id,
                                metadata={"score": comment.score, "type": "comment"},
                            )
                        )
            await asyncio.sleep(settings.reddit_poll_seconds)
    finally:
        await reddit.close()
