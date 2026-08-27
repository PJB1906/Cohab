"""Generate deterministic initial avatars for every seeded member.

Run: `python -m cohab.seed_avatars`          (everyone missing one)
     `python -m cohab.seed_avatars --force`   (regenerate all)

Why generated rather than downloaded (docs/DECISIONS.md D-13.10):

The obvious approach — pulling portraits from a placeholder API — fails two
tests. First, the free services that filter by nationality localise *names*,
not faces: `randomuser.me?nat=in` and `?nat=us` were verified to draw from
the same portrait pool (`women/92.jpg` appears under both), so "Indian
avatars" from that source would be a label on generic Western photographs.
Second, and more seriously, attaching photographs of real people to 1550
fabricated student profiles is not something that should ship anywhere near
a pilot.

So the Indian identity comes from the part of the data that is genuinely
Indian — the names the seed already generates (`seed.py::random_name` draws
from real Indian given names and surnames) — and the imagery is honestly
synthetic. Rendered locally with Pillow — no network — into the same
`/media/<name>` shape a real upload produces.

Gender tints the palette rather than deciding a face, which sidesteps the
question of what a "male" or "non-binary" portrait would even be.

Written as PNG, not SVG, on purpose: `services/uploads.py` deliberately
excludes SVG from `ALLOWED_CONTENT_TYPES` (D-10.2 — an SVG served from the
app's own origin can carry script), and seeded files land in the same
`/media` mount as genuine member uploads. Emitting a format the upload path
itself rejects would quietly punch a hole in that boundary.
"""

from __future__ import annotations

import argparse
import io
import uuid

from PIL import Image, ImageDraw, ImageFont
from sqlalchemy import select
from sqlalchemy.orm import Session

from cohab.db import SessionLocal
from cohab.models import User
from cohab.services.storage import get_image_storage

# Modal-palette grounds (frontend/src/index.css). Each is a dark surface with
# a phosphor-family foreground, so an avatar reads as part of the app rather
# than a foreign asset dropped into it.
PALETTES: dict[str, list[tuple[str, str]]] = {
    "female": [("#1c2a1a", "#aed2a4"), ("#17231f", "#9cbf93"), ("#1b2620", "#ddffdc")],
    "male": [("#181f25", "#8cab87"), ("#141d1c", "#9cbf93"), ("#1a2422", "#aed2a4")],
    "non_binary": [("#221c24", "#c9b8d4"), ("#1d2029", "#a8b6cf"), ("#231f1c", "#d4c2a8")],
}
FALLBACK = [("#181818", "#8cab87")]


def initials(full_name: str) -> str:
    parts = [p for p in full_name.strip().split() if p]
    if not parts:
        return "?"
    if len(parts) == 1:
        return parts[0][:2].upper()
    return (parts[0][0] + parts[-1][0]).upper()


def _stable_index(row_id: uuid.UUID, modulo: int) -> int:
    return int(row_id.hex[:8], 16) % modulo


SIZE = 256


def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Prefer a real face; fall back to Pillow's bitmap default rather than
    failing the whole seed on a machine without these fonts installed."""
    for candidate in ("segoeuib.ttf", "arialbd.ttf", "DejaVuSans-Bold.ttf"):
        try:
            return ImageFont.truetype(candidate, size)
        except OSError:
            continue
    return ImageFont.load_default()


def render_png(text: str, bg: str, fg: str) -> bytes:
    """A 256px square: flat ground, centred initials, nothing else.

    The ring that used to sit inside the edge is gone at the user's request.
    Every surface that renders an avatar already applies its own
    `rounded-full`, so the drawn circle was a second, slightly misaligned
    edge inside the real one rather than the frame it was meant to be.
    """
    image = Image.new("RGB", (SIZE, SIZE), bg)
    draw = ImageDraw.Draw(image)

    font = _font(104)
    # `anchor="mm"` centres on the glyph box, which is what keeps two-letter
    # initials optically centred rather than sitting low on the baseline.
    try:
        draw.text((SIZE // 2, SIZE // 2), text, font=font, fill=fg, anchor="mm")
    except ValueError:
        # The bitmap fallback font has no anchor support.
        box = draw.textbbox((0, 0), text, font=font)
        draw.text(
            ((SIZE - box[2] + box[0]) / 2, (SIZE - box[3] + box[1]) / 2),
            text,
            font=font,
            fill=fg,
        )

    buffer = io.BytesIO()
    image.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate initial avatars for seeded users.")
    parser.add_argument("--force", action="store_true", help="regenerate even if one exists")
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()

    storage = get_image_storage()

    session: Session = SessionLocal()
    try:
        query = select(User).order_by(User.created_at)
        if not args.force:
            query = query.where(User.avatar_url.is_(None))
        if args.limit:
            query = query.limit(args.limit)

        users = list(session.scalars(query))
        print(f"{len(users)} user(s) to process")

        for i, user in enumerate(users, 1):
            palette = PALETTES.get(user.gender, FALLBACK)
            bg, fg = palette[_stable_index(user.id, len(palette))]
            png = render_png(initials(user.full_name), bg, fg)

            name = f"avatar-{user.id.hex}.png"
            storage.save(name, png)
            user.avatar_url = f"/media/{name}"

            if i % 200 == 0:
                session.commit()
                print(f"  {i}/{len(users)}…")

        session.commit()
        print(f"\nDone. {len(users)} avatar(s) written, served at /media/<name>.")
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
