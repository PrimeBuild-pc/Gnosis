import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from gnosis.rag import RAG, cited_message_ids, valid_citations


def test_citation_validation():
    assert cited_message_ids("Dato [M12], confermato [M8].") == {8, 12}
    assert valid_citations("Dato [M12].", {12, 13})
    assert not valid_citations("Dato [M99].", {12, 13})
    assert not valid_citations("Nessuna fonte.", {12})


def test_discord_rag_passes_full_scope_before_generation():
    db = Mock()
    db.search.return_value = []
    llm = SimpleNamespace(embed_query=AsyncMock(return_value=[1.0]), text=AsyncMock())
    result = asyncio.run(
        RAG(db, llm).ask("q", workspace_id=7, discord_guild_id="101", source_external_ids=[])
    )
    db.search.assert_called_once_with(
        "q", [1.0], workspace_id=7, discord_guild_id="101", source_external_ids=[]
    )
    llm.text.assert_not_called()
    assert result["sources"] == []


@pytest.mark.parametrize("workspace,channels", [(None, ["10"]), (7, None)])
def test_incomplete_discord_scope_fails_before_embedding(workspace, channels):
    db = Mock()
    llm = SimpleNamespace(embed_query=AsyncMock())
    with pytest.raises(ValueError):
        asyncio.run(
            RAG(db, llm).ask(
                "q", workspace_id=workspace, discord_guild_id="101", source_external_ids=channels
            )
        )
    llm.embed_query.assert_not_called()
    db.search.assert_not_called()
