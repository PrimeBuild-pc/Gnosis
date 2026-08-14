from __future__ import annotations

import os
import tomllib
from collections.abc import Iterable
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
    chat_api_key: str = ""
    chat_base_url: str | None = None
    chat_model: str = "gpt-4o-mini"
    embedding_provider: str = "local"
    embedding_model: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    embedding_dimensions: int = 384
    telegram_api_id: int | None = None
    telegram_api_hash: str = ""
    telegram_session: str = "data/telegram/gnosis"
    telegram_bot_token: str = ""
    telegram_allowed_user_ids: tuple[int, ...] = field(default_factory=tuple)
    discord_bot_token: str = ""
    discord_allowed_role_ids: tuple[int, ...] = field(default_factory=tuple)
    digest_telegram_chat_id: str = ""
    digest_discord_webhook: str = ""
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
        openai_api_key = os.getenv("OPENAI_API_KEY", "")
        openai_base_url = os.getenv("OPENAI_BASE_URL") or None
        allowed_users = os.getenv("GNOSIS_TELEGRAM_ALLOWED_USERS", "")
        allowed_roles = os.getenv("GNOSIS_DISCORD_ALLOWED_ROLE_IDS", "")
        embedding_provider = os.getenv("GNOSIS_EMBEDDING_PROVIDER", cls.embedding_provider)
        embedding_model = (
            os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
            if embedding_provider == "openai"
            else os.getenv("GNOSIS_EMBEDDING_MODEL", cls.embedding_model)
        )
        return cls(
            database_url=os.getenv("DATABASE_URL", cls.database_url),
            openai_api_key=openai_api_key,
            openai_base_url=openai_base_url,
            chat_api_key=os.getenv("GNOSIS_CHAT_API_KEY", "").strip() or openai_api_key,
            chat_base_url=os.getenv("GNOSIS_CHAT_BASE_URL") or openai_base_url,
            chat_model=os.getenv("OPENAI_CHAT_MODEL", cls.chat_model),
            embedding_provider=embedding_provider,
            embedding_model=embedding_model,
            embedding_dimensions=int(
                os.getenv("GNOSIS_EMBEDDING_DIMENSIONS", str(cls.embedding_dimensions))
            ),
            telegram_api_id=int(api_id) if api_id else None,
            telegram_api_hash=os.getenv("TELEGRAM_API_HASH", ""),
            telegram_session=os.getenv("TELEGRAM_SESSION", cls.telegram_session),
            telegram_bot_token=os.getenv("TELEGRAM_BOT_TOKEN", ""),
            telegram_allowed_user_ids=tuple(
                int(value) for value in allowed_users.split(",") if value.strip()
            ),
            discord_bot_token=os.getenv("DISCORD_BOT_TOKEN", ""),
            discord_allowed_role_ids=tuple(
                int(value) for value in allowed_roles.split(",") if value.strip()
            ),
            digest_telegram_chat_id=os.getenv("GNOSIS_DIGEST_TELEGRAM_CHAT_ID", ""),
            digest_discord_webhook=os.getenv("GNOSIS_DIGEST_DISCORD_WEBHOOK", ""),
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


_ID_FIELDS = {"telegram": "chat_id", "discord": "channel_id", "reddit": "subreddit"}


def load_sources(path: Path) -> list[SourceConfig]:
    if not path.exists():
        raise FileNotFoundError(f"Configurazione sorgenti assente: {path}")
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    sources: list[SourceConfig] = []
    for platform, id_field in _ID_FIELDS.items():
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


def _toml_string(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def save_sources(path: Path, sources: Iterable[SourceConfig]) -> None:
    lines: list[str] = []
    for source in sources:
        id_field = _ID_FIELDS[source.platform]
        lines.append(f"[[{source.platform}]]")
        lines.append(f"{id_field} = {_toml_string(source.external_id)}")
        lines.append(f"name = {_toml_string(source.name)}")
        lines.append(f"enabled = {'true' if source.enabled else 'false'}")
        topics = ", ".join(_toml_string(topic) for topic in source.topics)
        lines.append(f"topics = [{topics}]")
        lines.append("")
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
