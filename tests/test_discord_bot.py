from gnosis.collectors.discord import is_authorized


def test_authorized_when_role_matches():
    assert is_authorized([42, 7], frozenset({7}))


def test_unauthorized_when_no_role_matches():
    assert not is_authorized([42, 7], frozenset({99}))


def test_unauthorized_when_no_roles():
    assert not is_authorized([], frozenset({7}))


def test_unauthorized_when_allowlist_empty():
    assert not is_authorized([7], frozenset())
