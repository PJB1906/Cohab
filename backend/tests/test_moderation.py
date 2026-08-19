"""Abuse-keyword flagging — pure, no DB."""

import pytest

from cohab.services.moderation import KeywordAbuseFlagger


@pytest.fixture()
def flagger() -> KeywordAbuseFlagger:
    return KeywordAbuseFlagger()


@pytest.mark.parametrize(
    "text",
    [
        "I'll kill you if you touch my stuff",
        "go kill yourself",
        "KILL YOU",
    ],
)
def test_flags_abusive_text(flagger: KeywordAbuseFlagger, text: str) -> None:
    assert flagger.flag(text) is True


@pytest.mark.parametrize(
    "text",
    [
        "hey, when are you free to see the place?",
        "can we split the deposit 50/50?",
        "",
        # Regression: an unanchored "rape" used to match inside ordinary
        # words (found in code review).
        "want some grapes? I bought too many",
        "that was a very therapeutic conversation, thanks",
    ],
)
def test_ignores_ordinary_text(flagger: KeywordAbuseFlagger, text: str) -> None:
    assert flagger.flag(text) is False
