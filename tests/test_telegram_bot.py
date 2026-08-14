from gnosis.telegram_bot import is_authorized


def test_authorized_user_is_allowed():
    assert is_authorized(42, frozenset({42, 7}))


def test_unknown_user_is_denied():
    assert not is_authorized(99, frozenset({42, 7}))


def test_missing_sender_is_denied():
    assert not is_authorized(None, frozenset({42}))


def test_empty_allowlist_denies_everyone():
    assert not is_authorized(42, frozenset())
