from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


@dataclass(frozen=True)
class CollectedMessage:
    platform: str
    source_external_id: str
    external_id: str
    author: str
    sent_at: datetime
    text: str
    url: str = ""
    thread_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.sent_at.tzinfo is None:
            object.__setattr__(self, "sent_at", self.sent_at.replace(tzinfo=UTC))
