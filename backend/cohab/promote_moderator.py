"""Grant `is_moderator` to an existing account by email.

Run: `python -m cohab.promote_moderator someone@example.com`

There is deliberately no API route for this (docs/DECISIONS.md D-7.1: the
moderation gate is the `is_moderator` flag on the caller's own account — an
HTTP endpoint that could set it would be a privilege-escalation hole). On a
fresh production DB nobody has that flag, so the first moderator has to be
granted this way, directly against the database, by whoever controls deploy
access. Re-run for further accounts as needed; a no-op if already granted.
"""

from __future__ import annotations

import sys

from sqlalchemy import select

from cohab.db import SessionLocal
from cohab.models import User


def promote(email: str) -> None:
    session = SessionLocal()
    try:
        user = session.scalar(select(User).where(User.email == email))
        if user is None:
            print(f"no account with email {email!r}")
            return
        if user.is_moderator:
            print(f"{email} is already a moderator")
            return
        user.is_moderator = True
        session.commit()
        print(f"granted is_moderator to {email}")
    finally:
        session.close()


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("usage: python -m cohab.promote_moderator <email>")
    promote(sys.argv[1])
