"""PII detection heuristics — pure, no DB."""

import pytest

from cohab.services.pii import detect_pii


@pytest.mark.parametrize(
    "text",
    [
        "call me on 9876543210",
        "98765 43210 works best after 6pm",
        "+91 98765 43210",
        "987-654-3210",
        "reach me at name.surname@example.com",
        "message me @roommate_hunter on insta",
        "wa.me/919876543210",
    ],
)
def test_detects_pii(text: str) -> None:
    assert detect_pii(text) is True


@pytest.mark.parametrize(
    "text",
    [
        "I usually get home around 7pm and cook dinner.",
        "I've lived with 3 roommates over 9 years, never an issue.",
        "Rent is 15000 and the deposit is 30000.",
        "",
        # Regression: an unanchored "insta" prefix used to match inside
        # ordinary words (found in code review).
        "I'll be there instantly, just wrapping up",
        "that's just an instance of bad luck with roommates",
    ],
)
def test_ignores_ordinary_text(text: str) -> None:
    assert detect_pii(text) is False
