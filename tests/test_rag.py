from gnosis.rag import cited_message_ids, valid_citations


def test_citation_validation():
    assert cited_message_ids("Dato [M12], confermato [M8].") == {8, 12}
    assert valid_citations("Dato [M12].", {12, 13})
    assert not valid_citations("Dato [M99].", {12, 13})
    assert not valid_citations("Nessuna fonte.", {12})
