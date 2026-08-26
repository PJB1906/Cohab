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
from cohab.models.matching import MatchScore
from cohab.models.safety import Moderator, Report
from cohab.seed import (
    LOCALITY_BUDGET_RANGE,
    make_attribute_weights,
    make_preference_profile,
    random_questionnaire,
)

# Read from the seed's own table rather than hardcoded, so this cannot drift
# out of sync with the localities the bulk pool actually uses — a mismatch
# would put the demo account in a city with no candidates to match against.
DEMO_LOCALITY = next(iter(LOCALITY_BUDGET_RANGE))

DEMO_EMAIL = "demo@christuniversity.in"
DEMO_PASSWORD = "demo-pass-1234"
OWNER_EMAIL = "puranjyoti.bera@msds.christuniversity.in"

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


def _ensure_demo_user(session: Session) -> User:
    user = session.scalar(select(User).where(User.email == DEMO_EMAIL))
    if user is not None:
        print(f"  demo user exists: {DEMO_EMAIL}")
    else:
        institution = session.scalar(select(Institution))
        if institution is None:
            sys.exit("No institution row — run the bulk seed (`python -m cohab.seed`) first.")
        user = User(
            institution=institution,
            email=DEMO_EMAIL,
            password_hash=hash_password(DEMO_PASSWORD),
            full_name="Demo Student",
            gender="female",
            seeker_type="needs_place",
            verification_status="verified",
            account_status="active",
            course="MSc Data Science, 2nd year",
        )
        session.add(user)
        session.flush()
        print(f"  created demo user: {DEMO_EMAIL} / {DEMO_PASSWORD}")

    # Moderator access — screens 14 (queue), report review, and analytics are
    # all gated on this single flag (App.tsx's ModeratorGate).
    if not user.is_moderator:
        user.is_moderator = True
        print("  granted is_moderator (unlocks Moderation + Analytics)")

    _ensure_profile(session, user, label="demo user")
    return user


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
    reporter = session.scalar(
        select(User).where(User.id.notin_([user.id, subject.id])).limit(1)
    )
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

        print("[1/4] Demo account")
        demo = _ensure_demo_user(session)
        session.flush()

        print("\n[2/4] Your own account")
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

        print("\n[3/4] Match states for the demo account")
        promoted = _promote_match_states(session, demo)

        print("\n[4/4] Thread, contact share, moderation case")
        if "chatting" in promoted:
            _seed_thread(session, demo, promoted["chatting"])
        if "contact_shared" in promoted:
            _seed_contact_share(session, demo, promoted["contact_shared"])
        _seed_open_report(session, demo)

        session.commit()
        print(f"\nDone.\n  Log in as: {DEMO_EMAIL} / {DEMO_PASSWORD}")
        if promoted:
            print("  Reachable states: " + ", ".join(sorted(promoted)))
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
