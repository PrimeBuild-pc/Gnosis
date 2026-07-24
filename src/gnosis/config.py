from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from zoneinfo import ZoneInfo


@dataclass(frozen=True)
class SourceConfig:
    platform: str
    external_id: str
    name: str
    enabled: bool = True
    topics: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class Settings:
    database_url: str = "postgresql://gnosis:gnosis@localhost:5432/gnosis"
    openai_api_key: str = ""
    openai_base_url: str | None = None
    chat_model: str = "gpt-4o-mini"
    embedding_model: str = "text-embedding-3-small"
    telegram_api_id: int | None = None
    telegram_api_hash: str = ""
    telegram_session: str = "data/telegram/gnosis"
    discord_bot_token: str = ""
    reddit_client_id: str = ""
    reddit_client_secret: str = ""
    reddit_user_agent: str = "gnosis-personal-kb/0.1"
    username: str = ""
    password: str = ""
    host: str = "127.0.0.1"
    port: int = 8080
    timezone: str = "Europe/Rome"
    sources_file: Path = Path("config/sources.toml")
    reddit_poll_seconds: int = 900
    process_seconds: int = 10
    relevance_threshold: float = 0.35

    @classmethod
    def from_env(cls) -> Settings:
        api_id = os.getenv("TELEGRAM_API_ID", "").strip()
        return cls(
            database_url=os.getenv("DATABASE_URL", cls.database_url),
            openai_api_key=os.getenv("OPENAI_API_KEY", ""),
            openai_base_url=os.getenv("OPENAI_BASE_URL") or None,
            chat_model=os.getenv("OPENAI_CHAT_MODEL", cls.chat_model),
            embedding_model=os.getenv("OPENAI_EMBEDDING_MODEL", cls.embedding_model),
            telegram_api_id=int(api_id) if api_id else None,
            telegram_api_hash=os.getenv("TELEGRAM_API_HASH", ""),
            telegram_session=os.getenv("TELEGRAM_SESSION", cls.telegram_session),
            discord_bot_token=os.getenv("DISCORD_BOT_TOKEN", ""),
            reddit_client_id=os.getenv("REDDIT_CLIENT_ID", ""),
            reddit_client_secret=os.getenv("REDDIT_CLIENT_SECRET", ""),
            reddit_user_agent=os.getenv("REDDIT_USER_AGENT", cls.reddit_user_agent),
            username=os.getenv("GNOSIS_USERNAME", ""),
            password=os.getenv("GNOSIS_PASSWORD", ""),
            host=os.getenv("GNOSIS_HOST", cls.host),
            port=int(os.getenv("GNOSIS_PORT", str(cls.port))),
            timezone=os.getenv("GNOSIS_TIMEZONE", cls.timezone),
            sources_file=Path(os.getenv("GNOSIS_SOURCES_FILE", str(cls.sources_file))),
            reddit_poll_seconds=int(os.getenv("GNOSIS_REDDIT_POLL_SECONDS", "900")),
            process_seconds=int(os.getenv("GNOSIS_PROCESS_SECONDS", "10")),
            relevance_threshold=float(os.getenv("GNOSIS_RELEVANCE_THRESHOLD", "0.35")),
        )

    @property
    def zoneinfo(self) -> ZoneInfo:
        return ZoneInfo(self.timezone)


def load_sources(path: Path) -> list[SourceConfig]:
    if not path.exists():
        raise FileNotFoundError(f"Configurazione sorgenti assente: {path}")
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    id_fields = {"telegram": "chat_id", "discord": "channel_id", "reddit": "subreddit"}
    sources: list[SourceConfig] = []
    for platform, id_field in id_fields.items():
        for item in data.get(platform, []):
            external_id = str(item.get(id_field, "")).strip()
            if not external_id:
                raise ValueError(f"{platform}: campo {id_field} obbligatorio")
            sources.append(
                SourceConfig(
                    platform=platform,
                    external_id=external_id,
                    name=str(item.get("name") or external_id),
                    enabled=bool(item.get("enabled", True)),
                    topics=tuple(map(str, item.get("topics", []))),
                )
            )
    if not sources:
        raise ValueError("La allowlist delle sorgenti è vuota")
    return sources
