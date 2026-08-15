from cohab.models import Base

EXPECTED_TABLES = {
    "institution",
    "user",
    "verification_record",
    "preference_profile",
    "user_attribute_weight",
    "listing",
    "weight_set",
    "match_score",
    "message",
    "contact_share",
    "feedback",
    "report",
    "moderator",
    "user_block",
    "consent_record",
}


def test_all_erd_tables_registered() -> None:
    assert EXPECTED_TABLES <= set(Base.metadata.tables.keys())


def test_match_score_has_ordered_pair_check() -> None:
    match_score = Base.metadata.tables["match_score"]
    check_names = {c.name for c in match_score.constraints if hasattr(c, "sqltext")}
    assert "ck_match_score_ordered_pair" in check_names
