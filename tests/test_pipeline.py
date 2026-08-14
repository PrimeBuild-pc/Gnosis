from datetime import UTC, datetime

from gnosis.pipeline import (
    chunk_text,
    content_hash,
    normalize_text,
    parse_classifications,
    parse_entities,
    store_collected,
)
from gnosis.types import CollectedMessage


class FakeDB:
    def __init__(self, ignored: bool = False) -> None:
        self.ignored = ignored
        self.saved = None

    def is_ignored(self, platform: str, author_id: str) -> bool:
        return self.ignored

    def save_message(self, source_id, message, content_hash):
        self.saved = (source_id, message, content_hash)
        return 42


def _message(author_id: str | None) -> CollectedMessage:
    return CollectedMessage(
        platform="telegram",
        source_external_id="1",
        external_id="10",
        author="someone",
        author_id=author_id,
        sent_at=datetime.now(UTC),
        text="hello world",
    )


def test_normalize_and_hash_are_stable():
    assert normalize_text(" a   b\r\n\n c ") == "a b\nc"
    assert content_hash("A   B") == content_hash("a b")


def test_chunk_text_has_bounded_chunks_and_overlap():
    text = "x" * 250
    chunks = chunk_text(text, size=100, overlap=20)
    assert len(chunks) == 3
    assert all(len(chunk) <= 100 for chunk in chunks)
    assert chunks[0][-20:] == chunks[1][:20]


def test_parse_classifications_rejects_unknown_and_clamps_score():
    parsed = parse_classifications(
        {
            "items": [
                {"id": 1, "relevance": 2, "tags": ["AI"], "kind": "news"},
                {"id": 9, "relevance": 1},
            ]
        },
        {1},
    )
    assert parsed == {1: {"relevance": 1.0, "tags": ["AI"], "kind": "news"}}


def test_store_collected_skips_ignored_author():
    db = FakeDB(ignored=True)
    result = store_collected(db, {("telegram", "1"): 5}, _message(author_id="99"))
    assert result is None
    assert db.saved is None


def test_store_collected_saves_when_author_not_ignored():
    db = FakeDB(ignored=False)
    result = store_collected(db, {("telegram", "1"): 5}, _message(author_id="99"))
    assert result == 42
    assert db.saved is not None


def test_store_collected_saves_when_author_id_missing():
    db = FakeDB(ignored=True)
    result = store_collected(db, {("telegram", "1"): 5}, _message(author_id=None))
    assert result == 42


def test_parse_entities_extracts_known_entities_and_relations():
    entities, relations = parse_entities(
        {
            "entities": [
                {"name": "Claude", "type": "tool"},
                {"name": "Anthropic", "type": "organization"},
            ],
            "relations": [{"source": "Claude", "target": "Anthropic", "relation": "made_by"}],
        }
    )
    assert entities == [("Claude", "tool"), ("Anthropic", "organization")]
    assert relations == [("Claude", "Anthropic", "made_by")]


def test_parse_entities_drops_relations_with_unknown_entities():
    entities, relations = parse_entities(
        {
            "entities": [{"name": "Claude", "type": "tool"}],
            "relations": [{"source": "Claude", "target": "Ghost", "relation": "made_by"}],
        }
    )
    assert entities == [("Claude", "tool")]
    assert relations == []


def test_parse_entities_drops_self_relations_and_dedupes_entities():
    entities, relations = parse_entities(
        {
            "entities": [
                {"name": "Claude", "type": "tool"},
                {"name": "Claude", "type": "tool"},
            ],
            "relations": [{"source": "Claude", "target": "Claude", "relation": "self"}],
        }
    )
    assert entities == [("Claude", "tool")]
    assert relations == []


def test_parse_entities_defaults_missing_type_and_ignores_malformed_items():
    entities, relations = parse_entities(
        {"entities": [{"name": "Widget"}, {"name": ""}], "relations": []}
    )
    assert entities == [("Widget", "concept")]
    assert relations == []
