"""memz's data (docs/memz/data_model.md, approved 2026-09-14).

Four groups: accounts (`MemzProfile` on the shared `User`), the bank
(`MemeImage`, `Pack`, `CaptionDeck`, `Topic`), a game (`Session` → `Player`
→ `Round` → `Submission` → `Vote`, plus `HandCard`), and output (`Meme`,
`SavedMeme`). Nothing here is shared with `app/`, `matazim/` or `ustrip/`;
the only foreign key out of this file is to `settings.AUTH_USER_MODEL`.
"""

import secrets

from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone

USER = settings.AUTH_USER_MODEL

# Session codes: letters and digits that cannot be confused when shouted
# across a room (spec §12.6). No 0/O, no 1/I.
CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def new_token(nbytes=24):
    return secrets.token_urlsafe(nbytes)


def new_share_slug():
    """128 bits, unguessable, never sequential (spec Rule 12.3.3.6)."""
    return secrets.token_urlsafe(16)


# ------------------------------------------------------------------ accounts


class MemzProfile(models.Model):
    """What memz knows about a person beyond "who is this" (Rule 2): tier.
    Created lazily on first use, never for every babook user."""

    FREE, PAID = "free", "paid"
    TIERS = [(FREE, "free"), (PAID, "paid")]

    user = models.OneToOneField(USER, on_delete=models.CASCADE, related_name="memz_profile")
    tier = models.CharField(max_length=8, choices=TIERS, default=FREE)
    display_name = models.CharField(max_length=40)
    paid_until = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.display_name} ({self.tier})"


# ------------------------------------------------------------------ the bank


class MemeImage(models.Model):
    """One picture in the bank. `owner` null means the public bank."""

    PUBLIC, PRIVATE = "public", "private"
    VISIBILITY = [(PUBLIC, "public"), (PRIVATE, "private")]
    PENDING, APPROVED, REJECTED = "pending", "approved", "rejected"
    MODERATION = [(PENDING, "pending"), (APPROVED, "approved"), (REJECTED, "rejected")]

    file = models.ImageField(upload_to="memz/images/%Y/%m/")
    title = models.CharField(max_length=120, blank=True)
    owner = models.ForeignKey(USER, null=True, blank=True, on_delete=models.CASCADE, related_name="memz_images")
    visibility = models.CharField(max_length=8, choices=VISIBILITY, default=PRIVATE)
    moderation_status = models.CharField(max_length=8, choices=MODERATION, default=PENDING)
    moderation_note = models.TextField(blank=True)
    # The file name in memz/seed_assets/, for the one-time seed. Empty for uploads.
    seed_key = models.CharField(max_length=200, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        constraints = [
            models.UniqueConstraint(fields=["seed_key"], condition=~Q(seed_key=""), name="memz_image_seed_key_unique"),
        ]

    def __str__(self):
        return self.title or self.seed_key or f"image {self.pk}"

    @property
    def is_dealable(self):
        """Rule 6.4.1: only approved images are ever dealt or shown."""
        return self.moderation_status == self.APPROVED


class Pack(models.Model):
    """The organizing unit of the bank. A public pack *is* a category."""

    name = models.CharField(max_length=80)
    slug = models.SlugField(max_length=80, allow_unicode=True)
    owner = models.ForeignKey(USER, null=True, blank=True, on_delete=models.CASCADE, related_name="memz_packs")
    is_public = models.BooleanField(default=False)
    description = models.CharField(max_length=200, blank=True)
    order = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    members = models.ManyToManyField(MemeImage, through="PackImage", related_name="packs", blank=True)

    class Meta:
        ordering = ["order", "name"]
        constraints = [
            models.UniqueConstraint(fields=["owner", "slug"], name="memz_pack_owner_slug_unique"),
            models.UniqueConstraint(fields=["slug"], condition=Q(owner__isnull=True), name="memz_public_pack_slug_unique"),
        ]

    def __str__(self):
        return self.name


class PackImage(models.Model):
    pack = models.ForeignKey(Pack, on_delete=models.CASCADE, related_name="images")
    image = models.ForeignKey(MemeImage, on_delete=models.CASCADE, related_name="pack_links")
    order = models.IntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]
        constraints = [models.UniqueConstraint(fields=["pack", "image"], name="memz_pack_image_unique")]


class CaptionDeck(models.Model):
    """Card mode content: a set of pre-written captions (spec §5.2)."""

    HEBREW, ENGLISH = "he", "en"
    LANGUAGES = [(HEBREW, "עברית"), (ENGLISH, "English")]

    name = models.CharField(max_length=80)
    owner = models.ForeignKey(USER, null=True, blank=True, on_delete=models.CASCADE, related_name="memz_decks")
    is_public = models.BooleanField(default=False)
    language = models.CharField(max_length=2, choices=LANGUAGES, default=HEBREW)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class CaptionCard(models.Model):
    deck = models.ForeignKey(CaptionDeck, on_delete=models.CASCADE, related_name="cards")
    text = models.CharField(max_length=140)
    order = models.IntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return self.text


class Topic(models.Model):
    """The theme for a round in Topics mode (spec §5.1)."""

    text = models.CharField(max_length=80)
    owner = models.ForeignKey(USER, null=True, blank=True, on_delete=models.CASCADE, related_name="memz_topics")
    is_public = models.BooleanField(default=False)
    language = models.CharField(max_length=2, choices=CaptionDeck.LANGUAGES, default=CaptionDeck.HEBREW)

    class Meta:
        ordering = ["text"]

    def __str__(self):
        return self.text


# -------------------------------------------------------------------- a game


class Session(models.Model):
    """One party session, from the moment a host opens it (spec §4)."""

    LOBBY, PLAYING, FINISHED, ABANDONED = "lobby", "playing", "finished", "abandoned"
    STATUSES = [(LOBBY, "lobby"), (PLAYING, "playing"), (FINISHED, "finished"), (ABANDONED, "abandoned")]
    ACTIVE = (LOBBY, PLAYING)

    NORMAL, TOPICS, SAME_MEME, RELAXED = "normal", "topics", "same_meme", "relaxed"
    GAME_MODES = [(NORMAL, "normal"), (TOPICS, "topics"), (SAME_MEME, "same_meme"), (RELAXED, "relaxed")]
    TYPED, CARDS = "typed", "cards"
    CAPTION_MODES = [(TYPED, "typed"), (CARDS, "cards")]
    VOTE, JUDGE = "vote", "judge"
    SCORING_MODES = [(VOTE, "vote"), (JUDGE, "judge")]
    PUBLIC_RANDOM, PACKS, OWN_ONLY, MIX = "public_random", "packs", "own_only", "mix"
    IMAGE_SOURCES = [(PUBLIC_RANDOM, "public_random"), (PACKS, "packs"), (OWN_ONLY, "own_only"), (MIX, "mix")]

    code = models.CharField(max_length=6)
    host_user = models.ForeignKey(USER, null=True, blank=True, on_delete=models.SET_NULL, related_name="memz_hosted")
    status = models.CharField(max_length=10, choices=STATUSES, default=LOBBY)
    game_mode = models.CharField(max_length=10, choices=GAME_MODES, default=NORMAL)
    caption_mode = models.CharField(max_length=6, choices=CAPTION_MODES, default=TYPED)
    scoring_mode = models.CharField(max_length=6, choices=SCORING_MODES, default=VOTE)
    image_source = models.CharField(max_length=14, choices=IMAGE_SOURCES, default=PUBLIC_RANDOM)
    packs = models.ManyToManyField(Pack, blank=True, related_name="sessions")
    deck = models.ForeignKey(CaptionDeck, null=True, blank=True, on_delete=models.SET_NULL, related_name="sessions")
    round_count = models.PositiveSmallIntegerField(default=5)
    round_seconds = models.PositiveSmallIntegerField(default=60)
    vote_seconds = models.PositiveSmallIntegerField(default=20)
    max_players = models.PositiveSmallIntegerField(default=5)
    remembered = models.BooleanField(default=False)
    # Bumped on every change; the state endpoint's ETag (spec §12.4).
    version = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    # "Play again" (spec Rule 4.8.1): the session this one was recreated
    # into, so a player's next poll here can find their new seat.
    next_session = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.SET_NULL, related_name="previous_session"
    )

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            # Unique among sessions that are still going; reusable afterwards (spec §12.6).
            models.UniqueConstraint(
                fields=["code"], condition=Q(status__in=("lobby", "playing")), name="memz_session_code_active_unique"
            ),
        ]

    def __str__(self):
        return f"{self.code} ({self.status})"


class Player(models.Model):
    """One seat in a session, and the answer to "who wrote what, without an
    account": the guest token (spec §3.1)."""

    session = models.ForeignKey(Session, on_delete=models.CASCADE, related_name="players")
    user = models.ForeignKey(USER, null=True, blank=True, on_delete=models.SET_NULL, related_name="memz_seats")
    nickname = models.CharField(max_length=16)
    guest_token = models.CharField(max_length=64, unique=True, default=new_token)
    is_host = models.BooleanField(default=False)
    seat_order = models.PositiveSmallIntegerField(default=0)
    score = models.IntegerField(default=0)
    # Cards mode (spec Rule 5.2.2): one mercy swap for a dead hand, once
    # per game.
    card_swap_used = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    # Not auto_now: presence (spec §4.9) needs this touched deliberately, on
    # a state fetch or an action, not on every incidental save (a score
    # update must not look like "just seen").
    last_seen_at = models.DateTimeField(default=timezone.now)
    joined_at = models.DateTimeField(auto_now_add=True)
    # Set when "Play again" (spec Rule 4.8.1) carries this player into the
    # new session's lobby automatically, same nickname, new token. Lets a
    # player's next poll on the *old* session discover where they went.
    carried_from = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.SET_NULL, related_name="carried_to"
    )

    class Meta:
        ordering = ["seat_order", "id"]
        constraints = [models.UniqueConstraint(fields=["session", "nickname"], name="memz_player_nickname_unique")]

    def __str__(self):
        return f"{self.nickname} in {self.session_id}"


class Round(models.Model):
    CAPTIONING, VOTING, REVEALED, DONE = "captioning", "voting", "revealed", "done"
    STATUSES = [(CAPTIONING, "captioning"), (VOTING, "voting"), (REVEALED, "revealed"), (DONE, "done")]

    session = models.ForeignKey(Session, on_delete=models.CASCADE, related_name="rounds")
    number = models.PositiveSmallIntegerField()
    topic = models.ForeignKey(Topic, null=True, blank=True, on_delete=models.SET_NULL, related_name="rounds")
    judge = models.ForeignKey(Player, null=True, blank=True, on_delete=models.SET_NULL, related_name="judged_rounds")
    status = models.CharField(max_length=10, choices=STATUSES, default=CAPTIONING)
    started_at = models.DateTimeField(null=True, blank=True)
    caption_deadline = models.DateTimeField(null=True, blank=True)
    reveal_deadline = models.DateTimeField(null=True, blank=True)
    vote_deadline = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["number"]
        constraints = [models.UniqueConstraint(fields=["session", "number"], name="memz_round_number_unique")]


class Submission(models.Model):
    """What one player made in one round. A row exists for every active
    player from the moment the round starts, carrying the dealt image; the
    meme arrives when they submit (data_model.md review change 1)."""

    round = models.ForeignKey(Round, on_delete=models.CASCADE, related_name="submissions")
    player = models.ForeignKey(Player, on_delete=models.CASCADE, related_name="submissions")
    image = models.ForeignKey(MemeImage, null=True, blank=True, on_delete=models.SET_NULL, related_name="dealt_in")
    meme = models.OneToOneField("Meme", null=True, blank=True, on_delete=models.SET_NULL, related_name="submission")
    submitted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["round", "player"], name="memz_submission_unique")]


class Vote(models.Model):
    round = models.ForeignKey(Round, on_delete=models.CASCADE, related_name="votes")
    voter = models.ForeignKey(Player, on_delete=models.CASCADE, related_name="votes_cast")
    submission = models.ForeignKey(Submission, on_delete=models.CASCADE, related_name="votes")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["round", "voter"], name="memz_vote_once_per_round")]


class HandCard(models.Model):
    """Which caption cards a player holds (card mode, spec §5.2)."""

    player = models.ForeignKey(Player, on_delete=models.CASCADE, related_name="hand")
    card = models.ForeignKey(CaptionCard, on_delete=models.CASCADE, related_name="in_hands")
    dealt_in_round = models.PositiveSmallIntegerField()
    played_in_round = models.PositiveSmallIntegerField(null=True, blank=True)


# -------------------------------------------------------------------- output


class Meme(models.Model):
    """A finished meme, whether from a game or from the solo creator. The
    rendered file is what a meme *is*; the bank image is a pointer."""

    GAME, SOLO = "game", "solo"
    SOURCES = [(GAME, "game"), (SOLO, "solo")]

    image = models.ForeignKey(MemeImage, null=True, blank=True, on_delete=models.SET_NULL, related_name="memes")
    caption_text = models.TextField()
    caption_card = models.ForeignKey(CaptionCard, null=True, blank=True, on_delete=models.SET_NULL, related_name="memes")
    rendered = models.ImageField(upload_to="memz/memes/%Y/%m/")
    source = models.CharField(max_length=4, choices=SOURCES, default=SOLO)
    created_by_user = models.ForeignKey(USER, null=True, blank=True, on_delete=models.SET_NULL, related_name="memz_memes")
    share_slug = models.CharField(max_length=32, unique=True, default=new_share_slug)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at", "-id"]

    def __str__(self):
        return self.caption_text[:40]


class SavedMeme(models.Model):
    user = models.ForeignKey(USER, on_delete=models.CASCADE, related_name="memz_saved")
    meme = models.ForeignKey(Meme, on_delete=models.CASCADE, related_name="saved_by")
    saved_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-saved_at", "-id"]
        constraints = [models.UniqueConstraint(fields=["user", "meme"], name="memz_saved_once_per_user")]
