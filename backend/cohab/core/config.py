"""Auth/session configuration — Phase 4. Plain module-level constants reading
`os.environ`, matching `db.py`'s existing style; no settings-framework
dependency for a handful of values.

The numeric defaults below (session length, OTP length/expiry) are not in
any spec document — proposed values, flagged as such in docs/DECISIONS.md.
"""

import os

from dotenv import load_dotenv

load_dotenv()

# Signs the session-cookie JWT. Required, like DATABASE_URL — there is no
# safe default for a secret that must differ per deployment.
SECRET_KEY = os.environ["SECRET_KEY"]

SESSION_COOKIE_NAME = "cohab_session"
SESSION_TTL_DAYS = 14  # proposed — not specified in any document

# CLAUDE.md: httpOnly, SameSite=Lax, Secure session cookie. `Secure` cookies
# are dropped by the browser over plain http, so local dev needs this False;
# any real deployment is same-origin https (CLAUDE.md) and must set it True.
COOKIE_SECURE = os.environ.get("COOKIE_SECURE", "True").strip().lower() == "true"

OTP_LENGTH = 6  # proposed — not specified in any document
OTP_TTL_MINUTES = 10  # proposed — not specified in any document
OTP_MAX_ATTEMPTS = 5  # proposed — not specified in any document

# Phase 5 photo uploads — local disk for the pilot (docs/DECISIONS.md): no
# object-storage service exists anywhere in this stack, and CLAUDE.md defers
# Redis on the same "no new infra the pilot doesn't need" grounds. Served
# back via the /media StaticFiles mount (cohab/main.py).
UPLOAD_DIR = os.environ.get("UPLOAD_DIR", "uploads")
MAX_UPLOAD_MB = 5  # proposed — not specified in any document

# Phase 6 chat rate limits (PRD §9.1 item 3: "the mechanical precondition for
# both spam and harassment is the ability to send unlimited messages to many
# people quickly"). Proposed values, not sourced from any document.
CHAT_RATE_LIMIT_PER_ACCOUNT_PER_MIN = 20
CHAT_RATE_LIMIT_PER_THREAD_PER_MIN = 30
