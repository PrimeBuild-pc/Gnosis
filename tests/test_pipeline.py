from gnosis.pipeline import chunk_text, content_hash, normalize_text, parse_classifications


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
