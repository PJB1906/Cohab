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

# Phase 11 addendum: real OTP email delivery via Resend, `services/otp.py`'s
# `get_otp_sender()`. Unset (the default) keeps the console-log sender every
# prior session used. `OTP_SENDER_EMAIL` defaults to Resend's own shared
# sandbox address, not a personal one — deliberately not the developer's
# email (docs/DECISIONS.md, Phase 11 addendum).
RESEND_API_KEY = os.environ.get("RESEND_API_KEY")
OTP_SENDER_EMAIL = os.environ.get("OTP_SENDER_EMAIL", "onboarding@resend.dev")

# Plain-SMTP alternative (checked first — see get_otp_sender): no domain
# verification needed, delivers to any recipient. Point at a throwaway
# mailbox's app-password SMTP (e.g. smtp.gmail.com:587), not a personal one.
SMTP_HOST = os.environ.get("SMTP_HOST")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER = os.environ.get("SMTP_USER")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD")

# `/auth/resend-otp` (docs/DECISIONS.md D-10.1/D-10.6) has no auth of its own
# — a cooldown between resends is the cheap guard against both spamming the
# OTP delivery mechanism and using rapid resends to keep resetting
# `otp_attempts`. Proposed, same footing as the constants above.
RESEND_OTP_COOLDOWN_SECONDS = 30

# Phase 5 photo uploads — local disk by default (docs/DECISIONS.md). Used by
# services/storage.py::LocalDiskStorage, still the fallback when the R2
# settings below aren't all set (dev, and CI/tests).
UPLOAD_DIR = os.environ.get("UPLOAD_DIR", "uploads")
MAX_UPLOAD_MB = 5  # proposed — not specified in any document

# Cloudflare R2 (S3-compatible) object storage — services/storage.py picks
# R2Storage over LocalDiskStorage when all four of these are set, so that
# uploaded images survive a redeploy on a host with no persistent disk.
R2_ENDPOINT_URL = os.environ.get("R2_ENDPOINT_URL")
R2_ACCESS_KEY_ID = os.environ.get("R2_ACCESS_KEY_ID")
R2_SECRET_ACCESS_KEY = os.environ.get("R2_SECRET_ACCESS_KEY")
R2_BUCKET_NAME = os.environ.get("R2_BUCKET_NAME")

# CLAUDE.md: "vite build, and FastAPI serves the static bundle" in prod.
# Relative to the backend process's cwd, same convention as UPLOAD_DIR —
# run.cmd (and any deploy script) starts uvicorn from backend/, so the
# default resolves to the frontend's build output one level up. Override if
# a deploy copies the built bundle elsewhere. Missing/absent is fine: main.py
# only serves it when the directory actually exists.
FRONTEND_DIST_DIR = os.environ.get("FRONTEND_DIST_DIR", "../frontend/dist")

# Phase 6 chat rate limits (PRD §9.1 item 3: "the mechanical precondition for
# both spam and harassment is the ability to send unlimited messages to many
# people quickly"). Proposed values, not sourced from any document.
CHAT_RATE_LIMIT_PER_ACCOUNT_PER_MIN = 20
CHAT_RATE_LIMIT_PER_THREAD_PER_MIN = 30

# Phase 7 report policy (PRD §8.3). The rate limit is a proposed value —
# PRD only says "report submission is rate limited" with no number.
# REPORT_AUTOSUSPEND_THRESHOLD is the one number PRD §8.3 actually gives:
# "three or more independent reports from unconnected users trigger
# automatic temporary suspension."
REPORT_RATE_LIMIT_PER_DAY = 5  # proposed — not specified in any document
REPORT_AUTOSUSPEND_THRESHOLD = 3
