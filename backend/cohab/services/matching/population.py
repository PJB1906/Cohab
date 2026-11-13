"""DB-free synthetic populations built from the v1 seed generator.

`seed.py` writes its profiles to Postgres; the v2 analyses (simulation,
power study, equivalence tests) need the same distribution in memory, many
times over, under different seeds. This reuses the seed's own generator
functions on transient ORM objects, so the populations are drawn from exactly
the distribution the v1 evaluation used, not a re-implementation of it.

Synthetic, and labelled so everywhere it is used (deck invariant 6).
"""

from __future__ import annotations

import random
import uuid

from cohab import seed as seed_module
from cohab.services.matching.candidate import Candidate


def synthetic_candidates(n: int, seed: int = 0, *, all_verified: bool = False) -> list[Candidate]:
    rng = random.Random(seed)
    institution = seed_module.make_institution()
    out: list[Candidate] = []
    for i in range(n):
        user = seed_module.make_user(rng, institution, i)
        user.id = uuid.UUID(int=rng.getrandbits(128))
        if all_verified:
            user.verification_status = "verified"
            user.account_status = "active"
        locality = seed_module.pick_target_locality(rng)
        profile = seed_module.make_preference_profile(rng, user, locality)
        user.attribute_weights = seed_module.make_attribute_weights(rng, user)
        listing = seed_module.make_listing(rng, user, locality) if user.seeker_type == "has_place" else None
        out.append(Candidate.from_orm(user, profile, listing))
    return out
