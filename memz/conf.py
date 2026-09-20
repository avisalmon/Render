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
    # SPR-Z.9 (2026-09-16): tightened from 100/2000 -- a scarce-enough number
    # to matter now that a free user's own uploads can be dealt into a
    # shared game other players join, not just their own private bank.
    # SPR-Z.11 (2026-09-19): 5 -> 30. Avi's own photos are now the *point*
    # ("the images are boring, I want every signed-in user to upload his
    # own"), and five is not a bank, it is a sample -- enough to run out
    # inside one game and be re-uploaded before the next.
    "UPLOAD_LIMIT": {"guest": 0, "free": 30, "paid": 50},
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
    # --- photo booth (SPR-W.2, spec §5.5) -----------------------------------
    # Thirty seconds of everyone photographing everyone. Long enough to
    # get a few real faces, short enough that it stays a burst rather
    # than a photo session -- the mode's whole charm is the scramble.
    "BOOTH_SECONDS": 30,
    # Each player may contribute this many; the pool needs roughly one
    # picture per player per round, and a room of four taking three each
    # covers a five-round game with room to spare.
    "BOOTH_PHOTOS_PER_PLAYER": 3,
    # Below this, there is nothing to play with and the booth refuses to
    # end the game into an empty pool.
    "BOOTH_MIN_PHOTOS": 2,
    # --- AI players (spec §4.11) --------------------------------------------
    "AI_PLAYERS_MAX": 3,
    "CAPTION_MAX_CHARS": 140,
    "CAPTION_MAX_LINES": 3,
    "NICKNAME_MAX_CHARS": 16,
    # 10s per meme (SPR-Z.10): the reveal is now also when everyone rates,
    # so this budget has to hold "read the joke AND tap a button", not just
    # "read the joke". Was 4s until ACT-Z.13 ("הרגע של חשיפה מאד קצר"),
    # then 8s for the few hours between ACT-Z.13 and SPR-Z.10.
    "REVEAL_SECONDS_PER_MEME": 10,
    # SPR-Z.10: how many times a player may throw back the image they were
    # dealt, per round, before they have to caption what they've got.
    "IMAGE_SWAPS_PER_ROUND": 3,
    "RESULT_AUTO_ADVANCE_SECONDS": 20,
    # --- presence (spec §4.9) ----------------------------------------------
    "AWAY_AFTER_SECONDS": 15,
    "INACTIVE_AFTER_SECONDS": 90,
    "ABANDON_AFTER_MINUTES": 10,
    # --- polling (spec Rule 11.6) ------------------------------------------
    "POLL_MS": {"lobby": 2000, "booth": 1000, "captioning": 1000, "voting": 1000, "results": 2000, "finished": 5000},
    # --- rendering (spec §8.1) ---------------------------------------------
    # The finished meme's own width stays 1080: it is the product's actual
    # output, shared to WhatsApp and sometimes opened on a laptop. Only the
    # encoder got tighter (ACT-Z.16): q85 -> q80 is 13% off every rendered
    # meme, and a round of 5 players x 5 rounds writes 25 of them.
    "RENDER_WIDTH": 1080,
    "RENDER_JPEG_QUALITY": 80,
    "RENDER_FONT_MAX": 64,
    "RENDER_FONT_MIN": 36,
    "UPLOAD_MAX_BYTES": 8 * 1024 * 1024,
    # ACT-Z.16 (2026-09-19): 1600 -> 1280, and an explicit quality knob.
    # Everything an upload becomes is bound for a phone screen, and the
    # widest it is ever drawn is RENDER_WIDTH (1080). A 12MP phone photo
    # measured 295 KB at 1600/q88 and 169 KB at 1280/q82 -- 43% less for
    # nothing anybody can see at arm's length. With the free quota now 30
    # uploads (SPR-Z.11), that is the difference between 100 users costing
    # 885 MB and 507 MB, on a 1 GB disk shared with the whole site.
    "UPLOAD_MAX_SIDE": 1280,
    "UPLOAD_JPEG_QUALITY": 82,
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
