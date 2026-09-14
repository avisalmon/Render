"""memz's tunables (spec §2.4, §4.2, §12.5).

Every number a person might want to change without a deploy lives here,
read from Django settings at call time so an env var on Render can override
it: `MEMZ_MAX_PLAYERS`, `MEMZ_GUEST_SESSION_TTL_HOURS` and so on. Nothing
here is data a person creates or edits, which is why it is configuration
and not a model (data_model.md, "Tier caps are not rows").

Per-tier values are dicts keyed by tier: `guest`, `free`, `paid`. `None`
means unlimited.
"""

from django.conf import settings

DEFAULTS = {
    # --- tiers (spec §2.4) --------------------------------------------------
    "MAX_PLAYERS": {"guest": 5, "free": 10, "paid": 50},
    "REMEMBERED_SESSIONS": {"guest": 0, "free": 30, "paid": None},
    "UPLOAD_LIMIT": {"guest": 0, "free": 100, "paid": 2000},
    "PACK_LIMIT": {"guest": 0, "free": 10, "paid": None},
    "GUEST_SESSION_TTL_HOURS": 48,
    "GUEST_MEME_TTL_HOURS": 48,
    # --- a game (spec §4.2, §5) ---------------------------------------------
    # (min, max, default)
    "ROUNDS": (3, 10, 5),
    "CAPTION_SECONDS": (30, 90, 60),
    "VOTE_SECONDS": (15, 45, 20),
    "HAND_SIZE": 7,
    "MIN_PLAYERS": {"vote": 3, "judge": 3, "relaxed": 2},
    "CAPTION_MAX_CHARS": 140,
    "CAPTION_MAX_LINES": 3,
    "NICKNAME_MAX_CHARS": 16,
    "REVEAL_SECONDS_PER_MEME": 4,
    "RESULT_AUTO_ADVANCE_SECONDS": 20,
    # --- presence (spec §4.9) ----------------------------------------------
    "AWAY_AFTER_SECONDS": 15,
    "INACTIVE_AFTER_SECONDS": 90,
    "ABANDON_AFTER_MINUTES": 10,
    # --- polling (spec Rule 11.6) ------------------------------------------
    "POLL_MS": {"lobby": 2000, "captioning": 1000, "voting": 1000, "results": 2000, "finished": 5000},
    # --- rendering (spec §8.1) ---------------------------------------------
    "RENDER_WIDTH": 1080,
    "RENDER_FONT_MAX": 64,
    "RENDER_FONT_MIN": 36,
    "UPLOAD_MAX_BYTES": 8 * 1024 * 1024,
    "UPLOAD_MAX_SIDE": 1600,
}


def get(name):
    """The value of one tunable, the setting `MEMZ_<name>` winning over the default."""
    if name not in DEFAULTS:
        raise KeyError(f"memz has no tunable named {name!r}")
    return getattr(settings, f"MEMZ_{name}", DEFAULTS[name])


def cap(name, tier):
    """A per-tier value. `None` means unlimited."""
    table = get(name)
    if tier not in table:
        raise KeyError(f"{name} has no value for tier {tier!r}")
    return table[tier]
