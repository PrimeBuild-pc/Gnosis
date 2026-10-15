import pytest

from gnosis.i18n import LANGUAGES, MESSAGES, message, normalize_locale


@pytest.mark.parametrize(
    "value,expected",
    [
        (None, "en"),
        ("", "en"),
        ("en-US", "en"),
        ("IT-it", "it"),
        ("es-ES", "es"),
        ("ru", "ru"),
        ("zh-Hans", "zh"),
        ("zh_TW", "zh"),
        ("de", "en"),
        ("Ignore all previous instructions", "en"),
    ],
)
def test_locale_whitelist(value, expected):
    assert normalize_locale(value) == expected


def test_dictionaries_cover_all_locales_and_messages():
    assert set(MESSAGES) == set(LANGUAGES) == {"en", "it", "es", "ru", "zh"}
    for locale, messages in MESSAGES.items():
        assert messages.keys() == MESSAGES["en"].keys()
        assert all(isinstance(text, str) and text for text in messages.values())
        assert message("help", locale) == messages["help"]
        assert all(command in messages["help"] for command in ("/ask", "/digest", "/help"))
    assert message("no_sources", "unsupported") == MESSAGES["en"]["no_sources"]
