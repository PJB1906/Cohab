"""Demo-path seeder — makes all 14 mockup screens reachable by clicking.

Run: `python -m cohab.demo_seed`

The bulk seed (`cohab/seed.py`) already produces a realistic pool: ~1550 users
and ~43k scored pairs. What it does *not* produce is a single account that can
walk every screen, because six of them are state-gated and one — the 30-day
check-in — needs a `cohabiting` match, of which a fresh seed has none. Without
that, screens 10 through 13 are unreachable in a demo no matter how much data
exists.

Design constraints this script holds to:

- **Additive only.** It creates one new user and promotes a handful of that
  user's own `match_score` rows. It never edits another member's profile, never
  deletes, and never touches the ~43k scores the evaluation chapter (Phase 9)
  is computed from. Re-running it is safe.
- **No invented scores.** Reaching `mutual`/`chatting`/`cohabiting` is a state
  transition on a pair the matcher already scored — this script promotes real
  rows rather than writing fake `combined_score` values, so every number on
  screen stays one the matcher actually produced.
- **Canonical pair order is respected** (`user_id_a < user_id_b`, CLAUDE.md) by
  reading existing rows rather than inserting new pairs.
"""

from __future__ import annotations

import sys
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from cohab.core.crypto import encrypt_message
from cohab.core.security import hash_password
from cohab.db import SessionLocal
from cohab.models import Institution, PreferenceProfile, User
from cohab.models.chat import ContactShare, Message
from cohab.models.matching import MatchScore, WeightSet
from cohab.models.safety import Moderator, Report
from cohab.seed import (
    LOCALITY_BUDGET_RANGE,
    make_attribute_weights,
    make_preference_profile,
    random_questionnaire,
)
from cohab.services.matches import MatchesService
from cohab.services.matching.recompute import _load_candidates
from cohab.services.matching.text import TfidfSimilarity

# Read from the seed's own table rather than hardcoded, so this cannot drift
# out of sync with the localities the bulk pool actually uses — a mismatch
# would put the demo account in a city with no candidates to match against.
DEMO_LOCALITY = next(iter(LOCALITY_BUDGET_RANGE))

DEMO_EMAIL = "demo@christuniversity.in"
DEMO_PASSWORD = "demo-pass-1234"
OWNER_EMAIL = "puranjyoti.bera@msds.christuniversity.in"

# Three single-purpose logins for manual testing: one of each seeker_type,
# plus a moderator account. seeker_type is NOT NULL in the schema (only
# "needs_place"/"has_place" — models/user.py), so the moderator account still
# needs one; it gets no PreferenceProfile since it's not meant to seek.
HAS_PLACE_EMAIL = "has-place-demo@christuniversity.in"
HAS_PLACE_PASSWORD = "has-place-pass-1234"
NEEDS_PLACE_EMAIL = "needs-place-demo@christuniversity.in"
NEEDS_PLACE_PASSWORD = "needs-place-pass-1234"
MODERATOR_EMAIL = "moderator-demo@christuniversity.in"
MODERATOR_PASSWORD = "moderator-pass-1234"

# One match promoted into each state the UI gates on. `suggested` is left
# alone — the bulk seed already provides 43k of those.
TARGET_STATES = ["viewed", "interested", "mutual", "chatting", "contact_shared", "cohabiting"]


def _rng():
    import random

    # Fixed seed: a demo that reshuffles every run is impossible to rehearse.
    return random.Random(20260825)


def _ensure_profile(session: Session, user: User, *, label: str) -> bool:
    """Give `user` a preference profile + weights if they have none.

    This is what unblocks the match list: without a `PreferenceProfile` the
    matcher has nothing to score, so `/matches` returns empty and `/profile`
    404s — exactly the symptom seen in the running app's backend log.
    """
    existing = session.scalar(
        select(PreferenceProfile).where(PreferenceProfile.user_id == user.id)
    )
    if existing is not None:
        print(f"  {label}: already has a preference profile — left untouched")
        return False

    rng = _rng()
    profile = make_preference_profile(rng, user, DEMO_LOCALITY)
    profile.questionnaire = random_questionnaire(rng)
    session.add(profile)
    for w in make_attribute_weights(rng, user):
        session.add(w)
    print(f"  {label}: created preference profile + attribute weights")
    return True


def _ensure_login(
    session: Session,
    *,
    email: str,
    password: str,
    full_name: str,
    gender: str,
    seeker_type: str,
    is_moderator: bool,
    with_profile: bool,
) -> User:
    user = session.scalar(select(User).where(User.email == email))
    if user is not None:
        print(f"  {email}: already exists")
    else:
        institution = session.scalar(select(Institution))
        if institution is None:
            sys.exit("No institution row — run the bulk seed (`python -m cohab.seed`) first.")
        user = User(
            institution=institution,
            email=email,
            password_hash=hash_password(password),
            full_name=full_name,
            gender=gender,
            seeker_type=seeker_type,
            verification_status="verified",
            account_status="active",
            course="MSc Data Science, 2nd year",
        )
        session.add(user)
        session.flush()
        print(f"  created: {email} / {password}")

    if is_moderator and not user.is_moderator:
        user.is_moderator = True
        print(f"  {email}: granted is_moderator (unlocks Moderation + Analytics)")

    if with_profile:
        _ensure_profile(session, user, label=email)
    return user


def _ensure_demo_user(session: Session) -> User:
    return _ensure_login(
        session,
        email=DEMO_EMAIL,
        password=DEMO_PASSWORD,
        full_name="Demo Student",
        gender="female",
        seeker_type="needs_place",
        is_moderator=True,
        with_profile=True,
    )


def _ensure_role_logins(session: Session) -> None:
    """Three single-purpose logins for manual testing (not part of the
    walk-every-screen demo account above)."""
    _ensure_login(
        session,
        email=HAS_PLACE_EMAIL,
        password=HAS_PLACE_PASSWORD,
        full_name="Has Place Demo",
        gender="female",
        seeker_type="has_place",
        is_moderator=False,
        with_profile=True,
    )
    _ensure_login(
        session,
        email=NEEDS_PLACE_EMAIL,
        password=NEEDS_PLACE_PASSWORD,
        full_name="Needs Place Demo",
        gender="male",
        seeker_type="needs_place",
        is_moderator=False,
        with_profile=True,
    )
    _ensure_login(
        session,
        email=MODERATOR_EMAIL,
        password=MODERATOR_PASSWORD,
        full_name="Moderator Demo",
        gender="female",
        seeker_type="needs_place",
        is_moderator=True,
        with_profile=False,
    )


def _pair_key(a: uuid.UUID, b: uuid.UUID) -> tuple[uuid.UUID, uuid.UUID]:
    return (a, b) if a < b else (b, a)


def _seed_role_login_chat(session: Session) -> None:
    """A short thread between the two role-only demo logins (screen 9),
    reachable without touching the walk-every-screen `demo` account.

    `_ensure_role_logins` gives both a `PreferenceProfile` generated by the
    same fixed-seed RNG (`_rng()` reseeds to the same value each call), so
    every field lands byte-identical between the two. That is eligibility
    poison for anything symmetric: `gender_preference` was a 1-in-3 draw
    that fails two times out of three (male vs male-preferred female, etc),
    and both profiles landed on `smoking_behaviour="indoors"` +
    `smoking_dealbreaker=True` — a self-conflict, since a dealbreaker check
    is symmetric and identical profiles always trip their own condition.
    Both are forced to a value that clears their own check, so the pair is
    eligible deterministically rather than depending on the shared draw.
    """
    has_place = session.scalar(select(User).where(User.email == HAS_PLACE_EMAIL))
    needs_place = session.scalar(select(User).where(User.email == NEEDS_PLACE_EMAIL))
    if has_place is None or needs_place is None:
        print("  role logins missing — skipped")
        return

    for u in (has_place, needs_place):
        profile = session.scalar(select(PreferenceProfile).where(PreferenceProfile.user_id == u.id))
        if profile is None:
            continue
        if profile.gender_preference != "any":
            profile.gender_preference = "any"
        if profile.smoking_dealbreaker:
            profile.smoking_dealbreaker = False
    session.flush()

    a_id, b_id = _pair_key(has_place.id, needs_place.id)
    row = session.scalar(
        select(MatchScore).where(MatchScore.user_id_a == a_id, MatchScore.user_id_b == b_id)
    )
    if row is None:
        # Real Stage 1 + Stage 2 scoring, same path `GET /matches` uses
        # (CLAUDE.md: no invented `combined_score` values) — not a full
        # `recompute`, just this one subject against the existing pool.
        weight_set = session.scalar(select(WeightSet).where(WeightSet.is_active.is_(True)))
        if weight_set is None:
            print("  no active weight_set — run the matcher/recompute first, skipped")
            return
        pool = _load_candidates(session)
        text_similarity = TfidfSimilarity().fit([c.lifestyle_notes for c in pool])
        service = MatchesService(session, weight_set, text_similarity)
        service.get_matches(has_place, limit=len(pool) or 1)
        row = session.scalar(
            select(MatchScore).where(MatchScore.user_id_a == a_id, MatchScore.user_id_b == b_id)
        )
    if row is None:
        print("  has-place/needs-place still not eligible against each other — skipped")
        return

    row.state = "chatting"
    row.interested_by_a = True
    row.interested_by_b = True
    session.flush()
    print(f"  role-login match {str(row.id)[:8]} -> chatting")
    _seed_thread(session, has_place, row.id)


def _promote_match_states(session: Session, user: User) -> dict[str, uuid.UUID]:
    """Move a few of this user's own scored pairs into the gated states."""
    rows = session.scalars(
        select(MatchScore)
        .where(or_(MatchScore.user_id_a == user.id, MatchScore.user_id_b == user.id))
        .where(MatchScore.state == "suggested")
        .order_by(MatchScore.combined_score.desc())
        .limit(len(TARGET_STATES))
    ).all()

    if not rows:
        print("  no `suggested` rows for this user — is the matcher run done?")
        return {}

    promoted: dict[str, uuid.UUID] = {}
    now = datetime.now(timezone.utc)
    for row, state in zip(rows, TARGET_STATES):
        row.state = state
        # Both-sides interest is what the UI reads to decide a match is mutual;
        # setting only the state would leave the detail screen inconsistent.
        if state in ("mutual", "chatting", "contact_shared", "cohabiting"):
            row.interested_by_a = True
            row.interested_by_b = True
        elif state == "interested":
            row.interested_by_a = True
        if state == "cohabiting":
            # `GET /feedback/pending` surfaces the 30-day check-in off this
            # timestamp, so it has to be genuinely ~30 days old.
            row.cohabiting_since = now - timedelta(days=31)
        promoted[state] = row.id
        print(f"  promoted match {str(row.id)[:8]} -> {state}")
    return promoted


def _seed_thread(session: Session, user: User, match_id: uuid.UUID) -> None:
    """A short readable conversation on the `chatting` match (screen 10)."""
    existing = session.scalar(
        select(func.count()).select_from(Message).where(Message.match_score_id == match_id)
    )
    if existing:
        print(f"  thread {str(match_id)[:8]} already has {existing} messages — skipped")
        return

    row = session.get(MatchScore, match_id)
    other_id = row.user_id_b if row.user_id_a == user.id else row.user_id_a
    base = datetime.now(timezone.utc) - timedelta(hours=20)
    script = [
        (other_id, "Hi — we matched. Are you still looking to move on 1 September?", 0),
        (user.id, "Yes, 1 September works. Is the room the one facing the balcony?", 21),
        (other_id, "That one. Morning light, and there is already a desk in it.", 34),
        (user.id, "Good. How do you and your current flatmate split the bills?", 800),
        (other_id, "Electricity and internet equally, cleaning help is ₹600 each.", 815),
    ]
    for sender_id, text, offset in script:
        session.add(
            Message(
                match_score_id=match_id,
                sender_id=sender_id,
                body_encrypted=encrypt_message(text),
                # `Message` timestamps via `CreatedAtMixin` — there is no
                # separate `sent_at` column.
                created_at=base + timedelta(minutes=offset),
                is_read=True,
            )
        )
    print(f"  seeded {len(script)} messages on the chatting thread")


def _seed_contact_share(session: Session, user: User, match_id: uuid.UUID) -> None:
    """One side consented on the `contact_shared` match (screen 11)."""
    existing = session.scalar(
        select(ContactShare).where(ContactShare.match_score_id == match_id)
    )
    if existing is not None:
        print("  contact share already recorded — skipped")
        return
    row = session.get(MatchScore, match_id)
    other_id = row.user_id_b if row.user_id_a == user.id else row.user_id_a
    session.add(
        ContactShare(
            match_score_id=match_id,
            user_id=other_id,
            consented_at=datetime.now(timezone.utc) - timedelta(hours=3),
        )
    )
    print("  seeded a one-sided contact share (the other party has agreed)")


def _seed_open_report(session: Session, user: User) -> None:
    """An open case so the moderator queue (screen 14) is not empty."""
    existing = session.scalar(
        select(func.count()).select_from(Report).where(Report.status == "open")
    )
    if existing:
        print(f"  {existing} open report(s) already in the queue — skipped")
        return

    subject = session.scalar(
        select(User).where(User.id != user.id, User.account_status == "active").limit(1)
    )
    if subject is None:
        print("  no other active user to report — skipped (seed pool too sparse)")
        return
    reporter = session.scalar(
        select(User).where(User.id.notin_([user.id, subject.id])).limit(1)
    )
    if reporter is None:
        print("  no third user to act as reporter — skipped (seed pool too sparse)")
        return
    session.add(
        Report(
            reporter_id=reporter.id,
            reported_user_id=subject.id,
            # Must be one of `REPORT_REASONS` (models/safety.py) — the API
            # validates against that tuple, so an invented value would create a
            # case the moderator screen cannot label.
            reason="inappropriate_behaviour",
            details="Asked to move the conversation to WhatsApp before we had shared contacts.",
            status="open",
            created_at=datetime.now(timezone.utc) - timedelta(hours=4),
        )
    )
    print(f"  opened a moderation case against {subject.full_name}")

    # `Moderator` is a separate row from the `is_moderator` flag; the queue's
    # claim action writes to it, so the demo account needs one.
    if session.scalar(select(Moderator).where(Moderator.user_id == user.id)) is None:
        session.add(Moderator(user_id=user.id, name=user.full_name, email=user.email))
        print("  registered demo user in the moderator table")


def main() -> None:
    session = SessionLocal()
    try:
        print("Demo seed — additive, safe to re-run.\n")

        print("[1/5] Demo account")
        demo = _ensure_demo_user(session)
        _ensure_role_logins(session)
        session.flush()

        print("\n[2/5] Your own account")
        owner = session.scalar(select(User).where(User.email == OWNER_EMAIL))
        if owner is None:
            print(f"  {OWNER_EMAIL} not found — skipped")
        else:
            _ensure_profile(session, owner, label=OWNER_EMAIL)
            if not owner.is_moderator:
                owner.is_moderator = True
                print("  granted is_moderator")
            if owner.verification_status != "verified":
                owner.verification_status = "verified"
                print("  marked verified")
        session.flush()

        print("\n[3/5] Match states for the demo account")
        promoted = _promote_match_states(session, demo)

        print("\n[4/5] Thread, contact share, moderation case")
        if "chatting" in promoted:
            _seed_thread(session, demo, promoted["chatting"])
        if "contact_shared" in promoted:
            _seed_contact_share(session, demo, promoted["contact_shared"])
        _seed_open_report(session, demo)

        print("\n[5/5] Chat between the has-place and needs-place role logins")
        _seed_role_login_chat(session)

        session.commit()
        print(f"\nDone.\n  Log in as: {DEMO_EMAIL} / {DEMO_PASSWORD}  (needs_place, moderator, walks every screen)")
        print(f"             {HAS_PLACE_EMAIL} / {HAS_PLACE_PASSWORD}  (has_place)")
        print(f"             {NEEDS_PLACE_EMAIL} / {NEEDS_PLACE_PASSWORD}  (needs_place)")
        print(f"             {MODERATOR_EMAIL} / {MODERATOR_PASSWORD}  (moderator only)")
        if promoted:
            print("  Reachable states: " + ", ".join(sorted(promoted)))
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
