"""Books' data (docs/books/data_model.md, approved 2026-10-18).

Built sprint by sprint. Nothing here touches another app's tables; the only
link to the shared User is Profile.
"""

from decimal import ROUND_HALF_UP, Decimal

from django.conf import settings
from django.db import models

from .storage import books_storage

# Two decimal places of latitude/longitude is about a kilometre: a
# neighbourhood, never a building (spec 12.9, data model section 9).
AREA_PLACES = Decimal("0.01")


def round_coordinate(value):
    if value is None:
        return None
    return Decimal(str(value)).quantize(AREA_PLACES, rounding=ROUND_HALF_UP)


class Profile(models.Model):
    """The person, inside Books (data model section 4)."""

    LANGUAGES = [("he", "עברית"), ("en", "English")]
    FREE, PLUS, PRO = "free", "plus", "pro"
    TIERS = [(FREE, "Free"), (PLUS, "Plus"), (PRO, "Pro")]
    # Appearance (spec BK1 §1.1b): the defaults Avi chose, everything else selectable.
    THEMES = [("light", "light"), ("dark", "dark"), ("system", "system")]
    PALETTES = [("lamplit", "lamplit"), ("warm", "warm"), ("bright", "bright"), ("den", "den")]
    SHELF_VIEWS = [("lamp", "lamp"), ("bookcase", "bookcase"), ("living", "living")]

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="books_profile")
    display_name = models.CharField(max_length=60)
    language = models.CharField(max_length=2, choices=LANGUAGES, default="he")
    tier = models.CharField(max_length=8, choices=TIERS, default=FREE)
    area_name = models.CharField(max_length=80, blank=True)
    area_lat = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    area_lng = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    radius_km = models.PositiveSmallIntegerField(default=10)
    is_adult_confirmed = models.BooleanField(default=False)
    accepted_terms_at = models.DateTimeField(null=True, blank=True)
    profile_public = models.BooleanField(default=False)
    show_points_public = models.BooleanField(default=False)
    theme = models.CharField(max_length=8, choices=THEMES, default="light")
    palette = models.CharField(max_length=8, choices=PALETTES, default="lamplit")
    shelf_view = models.CharField(max_length=10, choices=SHELF_VIEWS, default="lamp")
    # Spine titles read top to bottom instead of bottom to top (Avi, 2026-10-22).
    spine_text_down = models.BooleanField(default=False)
    # Shown to the other side of a deal only if this person chooses to (BK5).
    phone = models.CharField(max_length=30, blank=True)
    # What a public profile shows, each opt-in on its own (BK7, spec 12.9).
    public_library = models.BooleanField(default=False)
    public_reading = models.BooleanField(default=False)
    public_reviews = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["display_name"]

    def __str__(self):
        return self.display_name

    def save(self, *args, **kwargs):
        # Location is never stored precisely, whoever sets it and however.
        self.area_lat = round_coordinate(self.area_lat)
        self.area_lng = round_coordinate(self.area_lng)
        super().save(*args, **kwargs)


class Job(models.Model):
    """One unit of background work (books/jobs.py). Added in SPR-BK1.5; a
    data-model addition recorded in docs/books/data_model.md section 11."""

    QUEUED, RUNNING, DONE, FAILED = "queued", "running", "done", "failed"
    STATUSES = [(QUEUED, "queued"), (RUNNING, "running"), (DONE, "done"), (FAILED, "failed")]

    kind = models.CharField(max_length=40)
    ref_id = models.PositiveBigIntegerField(null=True, blank=True)
    profile = models.ForeignKey(Profile, on_delete=models.SET_NULL, null=True, blank=True, related_name="jobs")
    status = models.CharField(max_length=10, choices=STATUSES, default=QUEUED, db_index=True)
    attempts = models.PositiveSmallIntegerField(default=0)
    error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.kind} #{self.ref_id} {self.status}"


class ModelCall(models.Model):
    """One call to a paid model, with what it cost (spec BK1 §1.6). Added in
    SPR-BK1.5; recorded in data_model.md section 11."""

    profile = models.ForeignKey(Profile, on_delete=models.SET_NULL, null=True, blank=True, related_name="model_calls")
    job = models.ForeignKey(Job, on_delete=models.SET_NULL, null=True, blank=True, related_name="model_calls")
    provider = models.CharField(max_length=30)
    model = models.CharField(max_length=60)
    purpose = models.CharField(max_length=40)
    input_tokens = models.PositiveIntegerField(default=0)
    output_tokens = models.PositiveIntegerField(default=0)
    cost_usd = models.DecimalField(max_digits=8, decimal_places=5, default=0)
    duration_ms = models.PositiveIntegerField(default=0)
    ok = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.provider}/{self.model} {self.purpose} ${self.cost_usd}"


# ---- Foundation: the shared catalogue (data model section 3) ----------------


class CollectionType(models.Model):
    """What kind of thing is collected. Today one row: book."""

    key = models.SlugField(max_length=20, unique=True)
    name_he = models.CharField(max_length=60)
    name_en = models.CharField(max_length=60)
    condition_scale = models.CharField(max_length=20, default="book")

    def __str__(self):
        return self.key


class Creator(models.Model):
    """An author, translator, illustrator; later a mint or an engraver. A
    model, not a text column, so "books by this author" is a real query."""

    name = models.CharField(max_length=200)
    name_he = models.CharField(max_length=200, blank=True)
    name_en = models.CharField(max_length=200, blank=True)
    sort_name = models.CharField(max_length=200, blank=True)
    search_name = models.CharField(max_length=200, blank=True, db_index=True)
    source = models.CharField(max_length=30, blank=True)
    is_verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["sort_name", "name"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        from .textnorm import normalize

        self.search_name = normalize(self.name)[:200]
        if not self.sort_name:
            self.sort_name = self.name
        super().save(*args, **kwargs)


class CreatorAlias(models.Model):
    """Another spelling of the same person, so a Hebrew spine and an English
    record meet on one creator."""

    creator = models.ForeignKey(Creator, on_delete=models.CASCADE, related_name="aliases")
    name = models.CharField(max_length=200)
    search_name = models.CharField(max_length=200, blank=True, db_index=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["creator", "search_name"], name="books_alias_unique")]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        from .textnorm import normalize

        self.search_name = normalize(self.name)[:200]
        super().save(*args, **kwargs)


class Tag(models.Model):
    """Genre, subject, mood, audience, form. A controlled list, so two
    people's "thriller" is one tag. Drives browsing and, later, taste."""

    KINDS = [("genre", "genre"), ("subject", "subject"), ("mood", "mood"), ("audience", "audience"), ("form", "form")]

    kind = models.CharField(max_length=10, choices=KINDS, default="genre")
    key = models.SlugField(max_length=40, unique=True)
    name_he = models.CharField(max_length=80)
    name_en = models.CharField(max_length=80)
    parent = models.ForeignKey("self", on_delete=models.SET_NULL, null=True, blank=True, related_name="children")
    collection_type = models.ForeignKey(CollectionType, on_delete=models.CASCADE, null=True, blank=True,
                                        related_name="tags")

    class Meta:
        ordering = ["kind", "name_en"]

    def __str__(self):
        return self.key

    def tr(self, lang):
        return self.name_he if lang == "he" else self.name_en


class CatalogEntry(models.Model):
    """One shared, public record of a thing, the same for everyone. The
    book, not my book. Editions group under a parent work."""

    collection_type = models.ForeignKey(CollectionType, on_delete=models.PROTECT, related_name="entries")
    title = models.CharField(max_length=300)
    subtitle = models.CharField(max_length=300, blank=True)
    language = models.CharField(max_length=8, blank=True)
    year = models.PositiveSmallIntegerField(null=True, blank=True)
    description = models.TextField(blank=True)
    creators = models.ManyToManyField(Creator, through="EntryCreator", related_name="entries", blank=True)
    tags = models.ManyToManyField(Tag, related_name="entries", blank=True)
    cover = models.ImageField(upload_to="covers/%Y/%m/", storage=books_storage, blank=True)
    cover_source_url = models.URLField(max_length=500, blank=True)
    parent = models.ForeignKey("self", on_delete=models.SET_NULL, null=True, blank=True, related_name="editions")
    source = models.CharField(max_length=30, blank=True)
    source_ref = models.CharField(max_length=120, blank=True)
    confidence_note = models.CharField(max_length=200, blank=True)
    created_by = models.ForeignKey(Profile, on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name="catalog_entries")
    is_verified = models.BooleanField(default=False)
    merged_into = models.ForeignKey("self", on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name="merged_from")
    search_text = models.CharField(max_length=600, blank=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["title"]
        verbose_name_plural = "catalog entries"

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        from .textnorm import normalize

        if not self.pk or not self.search_text:
            self.search_text = normalize(f"{self.title} {self.subtitle}")[:600]
        super().save(*args, **kwargs)

    def refresh_search_text(self):
        """Title, subtitle and the creators, which only exist after the first save."""
        from .textnorm import normalize

        names = " ".join(c.name for c in self.creators.all())
        text = normalize(f"{self.title} {self.subtitle} {names}")[:600]
        CatalogEntry.objects.filter(pk=self.pk).update(search_text=text)
        self.search_text = text

    @property
    def creator_names(self):
        return ", ".join(c.name for c in self.creators.all())


class EntryCreator(models.Model):
    ROLES = [("author", "author"), ("translator", "translator"), ("illustrator", "illustrator"), ("editor", "editor")]

    entry = models.ForeignKey(CatalogEntry, on_delete=models.CASCADE, related_name="entry_creators")
    creator = models.ForeignKey(Creator, on_delete=models.CASCADE, related_name="entry_creators")
    role = models.CharField(max_length=12, choices=ROLES, default="author")
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["order"]
        constraints = [models.UniqueConstraint(fields=["entry", "creator", "role"], name="books_entrycreator_unique")]


class EntryIdentifier(models.Model):
    """The ways a record can be recognised. Many Israeli books have a danacode
    and no ISBN (spec 12.7)."""

    SCHEMES = [("isbn13", "ISBN-13"), ("isbn10", "ISBN-10"), ("danacode", "danacode"),
               ("openlibrary", "Open Library"), ("googlebooks", "Google Books"), ("nli", "National Library of Israel")]

    entry = models.ForeignKey(CatalogEntry, on_delete=models.CASCADE, related_name="identifiers")
    scheme = models.CharField(max_length=12, choices=SCHEMES)
    value = models.CharField(max_length=64)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["scheme", "value"], name="books_identifier_unique")]

    def __str__(self):
        return f"{self.scheme}:{self.value}"


class BookDetail(models.Model):
    """Facts only books have."""

    entry = models.OneToOneField(CatalogEntry, on_delete=models.CASCADE, related_name="book")
    publisher = models.CharField(max_length=200, blank=True)
    pages = models.PositiveIntegerField(null=True, blank=True)
    edition_statement = models.CharField(max_length=120, blank=True)
    binding = models.CharField(max_length=40, blank=True)
    original_language = models.CharField(max_length=8, blank=True)

    def __str__(self):
        return f"book facts for {self.entry_id}"


class EntryCorrection(models.Model):
    """A person's suggestion that a record is wrong; a curator accepts it
    (spec BK2 curation). Added in SPR-BK2.4, data model section 11."""

    OPEN, ACCEPTED, DECLINED = "open", "accepted", "declined"
    STATUSES = [(OPEN, "open"), (ACCEPTED, "accepted"), (DECLINED, "declined")]
    FIELDS = [("title", "title"), ("subtitle", "subtitle"), ("creators", "creators"), ("year", "year"),
              ("language", "language"), ("publisher", "publisher"), ("cover", "cover"), ("other", "other")]

    entry = models.ForeignKey(CatalogEntry, on_delete=models.CASCADE, related_name="corrections")
    profile = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name="corrections")
    field = models.CharField(max_length=12, choices=FIELDS, default="other")
    value = models.CharField(max_length=300, blank=True)
    note = models.CharField(max_length=500, blank=True)
    status = models.CharField(max_length=10, choices=STATUSES, default=OPEN, db_index=True)
    handled_by = models.ForeignKey(Profile, on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name="handled_corrections")
    created_at = models.DateTimeField(auto_now_add=True)
    handled_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.field} on {self.entry_id}: {self.status}"


# ---- Layer 1: the catalog (data model section 4) ------------------------------


class ShelfScan(models.Model):
    """One photo of a shelf, and the run that read it (BK3)."""

    UPLOADED, READING, REVIEW, DONE, FAILED = "uploaded", "reading", "review", "done", "failed"
    STATUSES = [(UPLOADED, "uploaded"), (READING, "reading"), (REVIEW, "review"), (DONE, "done"), (FAILED, "failed")]

    owner = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name="scans")
    photo = models.ImageField(upload_to="scans/%Y/%m/", storage=books_storage)
    shelf_label = models.CharField(max_length=120, blank=True)
    status = models.CharField(max_length=10, choices=STATUSES, default=UPLOADED, db_index=True)
    error = models.CharField(max_length=300, blank=True)
    model_name = models.CharField(max_length=60, blank=True)
    cost_usd = models.DecimalField(max_digits=8, decimal_places=5, default=0)
    seconds = models.DecimalField(max_digits=6, decimal_places=1, default=0)
    books_found = models.PositiveSmallIntegerField(default=0)
    books_accepted = models.PositiveSmallIntegerField(default=0)
    # The choices to start every book of this scan with (spec BK3).
    default_visibility = models.CharField(max_length=8, default="private")
    default_offers = models.CharField(max_length=40, blank=True, help_text="comma list of lend,exchange,sell")
    # One book held up to the camera, not a shelf: read as one image, not strips (Avi, 2026-10-21).
    is_single = models.BooleanField(default=False)
    # Where the book sits in a single-book photo, "x0,y0,x1,y1" as fractions; the crop becomes its picture.
    cover_box = models.CharField(max_length=60, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"scan {self.pk} by {self.owner_id}: {self.status}"


class ScanItem(models.Model):
    """One book the reader found on the photo, in shelf order."""

    PENDING, ACCEPTED, EDITED, SKIPPED = "pending", "accepted", "edited", "skipped"
    REVIEW = [(PENDING, "pending"), (ACCEPTED, "accepted"), (EDITED, "edited"), (SKIPPED, "skipped")]

    scan = models.ForeignKey(ShelfScan, on_delete=models.CASCADE, related_name="items")
    position = models.PositiveSmallIntegerField(default=0)
    raw_title = models.CharField(max_length=300, blank=True)
    raw_author = models.CharField(max_length=200, blank=True)
    added_by_hand = models.BooleanField(default=False)
    confidence = models.DecimalField(max_digits=4, decimal_places=3, default=0)
    review_status = models.CharField(max_length=8, choices=REVIEW, default=PENDING, db_index=True)
    copy = models.ForeignKey("Copy", on_delete=models.SET_NULL, null=True, blank=True, related_name="scan_items")

    class Meta:
        ordering = ["position"]

    def __str__(self):
        return f"{self.raw_title} ({self.review_status})"

    @property
    def raw_text(self):
        return f"{self.raw_title} | {self.raw_author}" if self.raw_author else self.raw_title


class ScanCandidate(models.Model):
    """The catalogue entries a spine may be, best first."""

    item = models.ForeignKey(ScanItem, on_delete=models.CASCADE, related_name="candidates")
    entry = models.ForeignKey(CatalogEntry, on_delete=models.CASCADE, related_name="scan_candidates")
    confidence = models.DecimalField(max_digits=4, decimal_places=3, default=0)
    rank = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["rank"]
        constraints = [models.UniqueConstraint(fields=["item", "entry"], name="books_candidate_unique")]


class Copy(models.Model):
    """One physical book one person owns. The same row moves to a new owner
    when it changes hands (data model decision)."""

    PRIVATE, PUBLIC = "private", "public"
    VISIBILITY = [(PRIVATE, "private"), (PUBLIC, "public")]
    WITH_OWNER, ON_LOAN_OUT, TRANSFERRED, LOST = "with_owner", "on_loan_out", "transferred", "lost"
    STATUSES = [(WITH_OWNER, "with owner"), (ON_LOAN_OUT, "on loan"), (TRANSFERRED, "transferred"), (LOST, "lost")]
    ADDED = [("scan", "scan"), ("manual", "manual"), ("import", "import"), ("received", "received")]

    owner = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name="copies")
    entry = models.ForeignKey(CatalogEntry, on_delete=models.PROTECT, related_name="copies")
    location_note = models.CharField(max_length=120, blank=True)
    position = models.PositiveIntegerField(default=0, help_text="order on the person's shelf")
    condition = models.CharField(max_length=20, blank=True)
    notes = models.TextField(blank=True)
    visibility = models.CharField(max_length=8, choices=VISIBILITY, default=PRIVATE)
    status = models.CharField(max_length=12, choices=STATUSES, default=WITH_OWNER, db_index=True)
    is_rare_candidate = models.BooleanField(default=False)
    rarity_note = models.CharField(max_length=300, blank=True)
    display_only = models.BooleanField(default=False)
    added_via = models.CharField(max_length=10, choices=ADDED, default="manual")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["position", "created_at"]
        verbose_name_plural = "copies"

    def __str__(self):
        return f"{self.entry} ({self.owner_id})"

    HELD = (WITH_OWNER, ON_LOAN_OUT)


class Offer(models.Model):
    """How a public copy is offered. One copy may carry several. An offer on
    a private copy is refused (data model section 9)."""

    LEND, EXCHANGE, SELL = "lend", "exchange", "sell"
    KINDS = [(LEND, "lend"), (EXCHANGE, "exchange"), (SELL, "sell")]

    copy = models.ForeignKey(Copy, on_delete=models.CASCADE, related_name="offers")
    kind = models.CharField(max_length=8, choices=KINDS)
    loan_days = models.PositiveSmallIntegerField(null=True, blank=True)
    price_amount = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    price_currency = models.CharField(max_length=3, default="ILS")
    wants_note = models.CharField(max_length=200, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["copy", "kind"], name="books_offer_one_per_kind")]

    def __str__(self):
        return f"{self.kind} {self.copy_id}"

    def clean(self):
        from django.core.exceptions import ValidationError

        if self.copy_id and self.copy.visibility != Copy.PUBLIC:
            raise ValidationError("An offer needs a public copy.")

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)


class CopyPhoto(models.Model):
    """Photos of one copy: the cover, the copyright page, a signature, damage.
    Private to the owner (and, from BK5, to the other side of a deal)."""

    KINDS = [("cover", "cover"), ("copyright_page", "copyright page"), ("signed", "signed"), ("other", "other")]

    copy = models.ForeignKey(Copy, on_delete=models.CASCADE, related_name="photos")
    image = models.ImageField(upload_to="copies/%Y/%m/", storage=books_storage)
    kind = models.CharField(max_length=16, choices=KINDS, default="other")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]


class Wish(models.Model):
    """A book a person wants (BK4 list; BK5 alerts)."""

    profile = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name="wishes")
    entry = models.ForeignKey(CatalogEntry, on_delete=models.CASCADE, null=True, blank=True, related_name="wishes")
    free_text = models.CharField(max_length=300, blank=True)
    notify_when_available = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [models.UniqueConstraint(fields=["profile", "entry"], name="books_wish_once",
                                               condition=models.Q(entry__isnull=False))]

    def __str__(self):
        return self.entry.title if self.entry_id else self.free_text


# ---- Layer 2: the hub (data model section 5) -----------------------------------


class MeetingPlace(models.Model):
    """A named handover point (a cafe, a library, a bookshop). The place's own
    coordinates, never a person's."""

    KINDS = [("cafe", "cafe"), ("library", "library"), ("bookshop", "bookshop"), ("other", "other")]

    name = models.CharField(max_length=120)
    kind = models.CharField(max_length=10, choices=KINDS, default="other")
    area_name = models.CharField(max_length=80, blank=True)
    lat = models.DecimalField(max_digits=8, decimal_places=5, null=True, blank=True)
    lng = models.DecimalField(max_digits=8, decimal_places=5, null=True, blank=True)
    is_partner = models.BooleanField(default=False)
    notes = models.CharField(max_length=300, blank=True)
    is_active = models.BooleanField(default=True)
    circle = models.ForeignKey("Circle", on_delete=models.CASCADE, null=True, blank=True,
                               related_name="meeting_places", help_text="a circle's own place; empty means everyone's")

    class Meta:
        ordering = ["area_name", "name"]

    def __str__(self):
        return f"{self.name}, {self.area_name}" if self.area_name else self.name


class Deal(models.Model):
    """One person asking for one offered copy, and what happened (lend,
    exchange and sale in one model). `copy` and `owner` are kept even though
    the offer gives them: after a transfer the copy's owner changes, and the
    deal must still say who owned it then."""

    REQUESTED, APPROVED, DECLINED, CANCELLED = "requested", "approved", "declined", "cancelled"
    HANDED_OVER, RETURNED, COMPLETED, LOST, DISPUTED = "handed_over", "returned", "completed", "lost", "disputed"
    STATUSES = [(REQUESTED, "requested"), (APPROVED, "approved"), (DECLINED, "declined"), (CANCELLED, "cancelled"),
                (HANDED_OVER, "handed over"), (RETURNED, "returned"), (COMPLETED, "completed"), (LOST, "lost"),
                (DISPUTED, "disputed")]
    OPEN = (REQUESTED, APPROVED, HANDED_OVER, DISPUTED)

    offer = models.ForeignKey(Offer, on_delete=models.SET_NULL, null=True, blank=True, related_name="deals")
    copy = models.ForeignKey(Copy, on_delete=models.PROTECT, related_name="deals")
    owner = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name="deals_as_owner")
    requester = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name="deals_as_requester")
    kind = models.CharField(max_length=8, choices=Offer.KINDS)
    status = models.CharField(max_length=12, choices=STATUSES, default=REQUESTED, db_index=True)
    swap_copy = models.ForeignKey(Copy, on_delete=models.SET_NULL, null=True, blank=True, related_name="swap_deals")
    loan_days = models.PositiveSmallIntegerField(null=True, blank=True)
    price_amount = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    due_date = models.DateField(null=True, blank=True)
    meeting_place = models.ForeignKey(MeetingPlace, on_delete=models.SET_NULL, null=True, blank=True,
                                      related_name="deals")
    meeting_note = models.CharField(max_length=300, blank=True)
    owner_confirmed_handover_at = models.DateTimeField(null=True, blank=True)
    requester_confirmed_handover_at = models.DateTimeField(null=True, blank=True)
    requester_marked_returned_at = models.DateTimeField(null=True, blank=True)
    returned_confirmed_at = models.DateTimeField(null=True, blank=True)
    returned_late = models.BooleanField(default=False)
    # Ways to talk each side chose to open after approval: phone, whatsapp, email.
    owner_shares = models.CharField(max_length=40, blank=True)
    requester_shares = models.CharField(max_length=40, blank=True)
    closed_note = models.CharField(max_length=300, blank=True)
    reminded = models.CharField(max_length=40, blank=True, help_text="reminders already sent: soon,due,lost")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self):
        return f"{self.kind} {self.copy_id} {self.status}"

    def other(self, profile):
        return self.requester if profile.pk == self.owner_id else self.owner

    def role(self, profile):
        if profile.pk == self.owner_id:
            return "owner"
        if profile.pk == self.requester_id:
            return "requester"
        return None


class Message(models.Model):
    deal = models.ForeignKey(Deal, on_delete=models.CASCADE, related_name="messages")
    sender = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name="messages_sent")
    body = models.TextField(max_length=2000)
    created_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["created_at"]


class CopyTransfer(models.Model):
    """A copy changing hands: the same row moves to its new owner, and this
    records the move (data model decision; provenance for the museum)."""

    KINDS = [("sold", "sold"), ("given", "given"), ("exchanged", "exchanged")]

    copy = models.ForeignKey(Copy, on_delete=models.CASCADE, related_name="transfers")
    from_profile = models.ForeignKey(Profile, on_delete=models.SET_NULL, null=True, related_name="transfers_out")
    to_profile = models.ForeignKey(Profile, on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name="transfers_in")
    deal = models.ForeignKey(Deal, on_delete=models.SET_NULL, null=True, blank=True, related_name="transfers")
    kind = models.CharField(max_length=10, choices=KINDS)
    transferred_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["transferred_at"]


class Block(models.Model):
    blocker = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name="blocks_made")
    blocked = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name="blocks_received")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["blocker", "blocked"], name="books_block_once")]


class Notification(models.Model):
    """In the app only (Avi, 2026-10-19). The words come from the catalogue
    by `kind`, in the reader's language, so nothing is stored in one tongue."""

    profile = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name="notifications")
    kind = models.CharField(max_length=30)
    deal = models.ForeignKey(Deal, on_delete=models.CASCADE, null=True, blank=True, related_name="notifications")
    entry = models.ForeignKey(CatalogEntry, on_delete=models.CASCADE, null=True, blank=True,
                              related_name="notifications")
    copy = models.ForeignKey(Copy, on_delete=models.CASCADE, null=True, blank=True, related_name="notifications")
    thread = models.ForeignKey("Thread", on_delete=models.CASCADE, null=True, blank=True, related_name="notifications")
    scan = models.ForeignKey(ShelfScan, on_delete=models.CASCADE, null=True, blank=True, related_name="notifications")
    badge = models.ForeignKey("Badge", on_delete=models.CASCADE, null=True, blank=True, related_name="notifications")
    exhibit_item = models.ForeignKey("ExhibitItem", on_delete=models.CASCADE, null=True, blank=True,
                                     related_name="notifications")
    read_at = models.DateTimeField(null=True, blank=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]


class Report(models.Model):
    """A report button for anything (spec 12.10). Posts and reviews join in BK7."""

    OPEN, HANDLED = "open", "handled"

    reporter = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name="reports_made")
    copy = models.ForeignKey(Copy, on_delete=models.SET_NULL, null=True, blank=True, related_name="reports")
    profile = models.ForeignKey(Profile, on_delete=models.SET_NULL, null=True, blank=True,
                                related_name="reports_about")
    deal = models.ForeignKey(Deal, on_delete=models.SET_NULL, null=True, blank=True, related_name="reports")
    post = models.ForeignKey("Post", on_delete=models.SET_NULL, null=True, blank=True, related_name="reports")
    review = models.ForeignKey("Review", on_delete=models.SET_NULL, null=True, blank=True, related_name="reports")
    reason = models.CharField(max_length=500)
    status = models.CharField(max_length=10, default=OPEN, db_index=True)
    handled_by = models.ForeignKey(Profile, on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name="reports_handled")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]


# ---- circles and the first launch (BK6) --------------------------------------------------

class Circle(models.Model):
    """A group of people (book club, school, workplace, neighbourhood). Its
    members see each other's offered books even beyond their radius. A
    private circle is joined only with its link or code; an open one is
    listed and anyone may join."""

    KINDS = [("club", "book club"), ("school", "school"), ("work", "workplace"),
             ("neighbourhood", "neighbourhood"), ("other", "other")]

    name = models.CharField(max_length=80)
    kind = models.CharField(max_length=14, choices=KINDS, default="club")
    area_name = models.CharField(max_length=80, blank=True)
    description = models.CharField(max_length=500, blank=True)
    join_code = models.CharField(max_length=12, unique=True)
    is_private = models.BooleanField(default=True)
    created_by = models.ForeignKey(Profile, on_delete=models.SET_NULL, null=True, related_name="circles_created")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class CircleMember(models.Model):
    MEMBER, MODERATOR, OWNER = "member", "moderator", "owner"
    ROLES = [(MEMBER, "member"), (MODERATOR, "moderator"), (OWNER, "owner")]

    circle = models.ForeignKey(Circle, on_delete=models.CASCADE, related_name="members")
    profile = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name="circle_memberships")
    role = models.CharField(max_length=10, choices=ROLES, default=MEMBER)
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["joined_at"]
        constraints = [models.UniqueConstraint(fields=["circle", "profile"], name="books_circle_member_once")]

    @property
    def can_moderate(self):
        return self.role in (self.MODERATOR, self.OWNER)


class Feedback(models.Model):
    """A few words from inside the app, straight to Avi (spec BK6). The page
    it was written on is kept so the words have their context."""

    OPEN, READ = "open", "read"

    profile = models.ForeignKey(Profile, on_delete=models.SET_NULL, null=True, related_name="feedback")
    path = models.CharField(max_length=300, blank=True)
    body = models.TextField(max_length=2000)
    status = models.CharField(max_length=8, default=OPEN, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name_plural = "feedback"


# ---- community (BK7) ----------------------------------------------------------------------------

class Thread(models.Model):
    """A discussion, a blog piece or a book report. Forums and blogs are one
    structure with a `kind` (data model section 6). `circle` empty means
    open to everyone in Books; set, it is that circle's own and only its
    members read it."""

    DISCUSSION, BLOG, REPORT = "discussion", "blog", "report"
    KINDS = [(DISCUSSION, "discussion"), (BLOG, "blog"), (REPORT, "book report")]

    kind = models.CharField(max_length=10, choices=KINDS, default=DISCUSSION, db_index=True)
    circle = models.ForeignKey(Circle, on_delete=models.CASCADE, null=True, blank=True, related_name="threads")
    author = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name="threads")
    title = models.CharField(max_length=160)
    entry = models.ForeignKey(CatalogEntry, on_delete=models.SET_NULL, null=True, blank=True, related_name="threads")
    is_locked = models.BooleanField(default=False)
    is_pinned = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    last_post_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-is_pinned", "-last_post_at"]

    def __str__(self):
        return self.title


class Post(models.Model):
    """The first post of a blog or report thread is the piece itself; the
    rest are comments. Hidden is reversible (a moderator); deleted is the
    author's own choice and is final."""

    VISIBLE, HIDDEN = "visible", "hidden"
    STATUSES = [(VISIBLE, "visible"), (HIDDEN, "hidden")]

    thread = models.ForeignKey(Thread, on_delete=models.CASCADE, related_name="posts")
    author = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name="posts")
    body = models.TextField(max_length=20000)
    status = models.CharField(max_length=8, choices=STATUSES, default=VISIBLE, db_index=True)
    hidden_by = models.ForeignKey(Profile, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)
    edited_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["created_at"]


class Review(models.Model):
    """A short opinion of a book, one per person per book. Longer analysis
    is a `report` thread."""

    VISIBLE, HIDDEN = "visible", "hidden"

    profile = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name="reviews")
    entry = models.ForeignKey(CatalogEntry, on_delete=models.CASCADE, related_name="reviews")
    rating = models.PositiveSmallIntegerField()
    body = models.TextField(max_length=4000, blank=True)
    has_spoilers = models.BooleanField(default=False)
    status = models.CharField(max_length=8, default=VISIBLE, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [models.UniqueConstraint(fields=["profile", "entry"], name="books_review_one_per_book")]


class ReadingLog(models.Model):
    """What a person says they read, on trust, private by default (spec 12.9)."""

    WANT, READING, READ, DNF = "want", "reading", "read", "dnf"
    STATUSES = [(WANT, "want to read"), (READING, "reading"), (READ, "read"), (DNF, "did not finish")]

    profile = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name="reading")
    entry = models.ForeignKey(CatalogEntry, on_delete=models.CASCADE, related_name="reading")
    status = models.CharField(max_length=8, choices=STATUSES, db_index=True)
    started_on = models.DateField(null=True, blank=True)
    finished_on = models.DateField(null=True, blank=True)
    note = models.CharField(max_length=500, blank=True)
    # My count of the book's pages, when it differs from the catalogue's (Avi, 2026-10-21).
    pages = models.PositiveIntegerField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]
        constraints = [models.UniqueConstraint(fields=["profile", "entry"], name="books_reading_one_per_book")]


# ---- play (BK8) ------------------------------------------------------------------------------

class ReadingCheckin(models.Model):
    """One row per day the person says they read. The streak is computed
    from these and the freezes, never stored (data model section 6)."""

    profile = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name="checkins")
    day = models.DateField()
    minutes = models.PositiveSmallIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-day"]
        constraints = [models.UniqueConstraint(fields=["profile", "day"], name="books_checkin_once_a_day")]


class StreakFreeze(models.Model):
    """Earned by a week of reading; spent on a missed day so the streak
    survives it (the Duolingo freeze, spec 12.5)."""

    profile = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name="freezes")
    earned_at = models.DateTimeField(auto_now_add=True)
    used_on = models.DateField(null=True, blank=True, db_index=True)

    class Meta:
        ordering = ["earned_at"]


class PointEvent(models.Model):
    """Points are a ledger: one row per award, the total is the sum, nothing
    is overwritten, and any award can be reversed (data model decision)."""

    KINDS = [("handover_confirmed", "handover confirmed"), ("returned_on_time", "returned on time"),
             ("review", "review"), ("report", "book report"), ("catalog_confirm", "catalogue confirm"),
             ("adjustment", "adjustment")]

    profile = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name="points")
    kind = models.CharField(max_length=20, choices=KINDS, db_index=True)
    points = models.IntegerField()
    deal = models.ForeignKey("Deal", on_delete=models.SET_NULL, null=True, blank=True, related_name="points")
    review = models.ForeignKey("Review", on_delete=models.SET_NULL, null=True, blank=True, related_name="points")
    thread = models.ForeignKey("Thread", on_delete=models.SET_NULL, null=True, blank=True, related_name="points")
    entry = models.ForeignKey(CatalogEntry, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    note = models.CharField(max_length=200, blank=True)
    reversed_at = models.DateTimeField(null=True, blank=True, db_index=True)
    reversed_by = models.ForeignKey(Profile, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [models.UniqueConstraint(fields=["profile", "kind", "deal"], condition=models.Q(deal__isnull=False),
                                               name="books_points_one_deal_once")]


class Badge(models.Model):
    """A milestone. Created on first award from the definitions in
    books/play.py; the words live here so they can be edited in admin."""

    key = models.CharField(max_length=40, unique=True)
    name_he = models.CharField(max_length=80)
    name_en = models.CharField(max_length=80)
    about_he = models.CharField(max_length=200, blank=True)
    about_en = models.CharField(max_length=200, blank=True)

    def __str__(self):
        return self.key


class ProfileBadge(models.Model):
    profile = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name="badges")
    badge = models.ForeignKey(Badge, on_delete=models.CASCADE, related_name="holders")
    earned_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-earned_at"]
        constraints = [models.UniqueConstraint(fields=["profile", "badge"], name="books_badge_once")]


# ---- discovery (BK9) ---------------------------------------------------------------------------

class EntryTagging(models.Model):
    """How a record got its tags: by the tagging model (with its cost and
    confidence) or by a curator. One row per record; a curator's choice is
    never overwritten by the model."""

    MODEL, CURATOR = "model", "curator"

    entry = models.OneToOneField(CatalogEntry, on_delete=models.CASCADE, related_name="tagging")
    source = models.CharField(max_length=8, default=MODEL)
    model_name = models.CharField(max_length=60, blank=True)
    confidence = models.DecimalField(max_digits=4, decimal_places=3, default=0)
    raw = models.JSONField(default=dict, blank=True, help_text="the model's answer, for audit only")
    tagged_at = models.DateTimeField(auto_now=True)


class ProfileTaste(models.Model):
    """What a person likes, per tag (data model section 6): from the survey
    they answered, and derived from their library, log and reviews."""

    SURVEY, DERIVED = "survey", "derived"

    profile = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name="taste")
    tag = models.ForeignKey(Tag, on_delete=models.CASCADE, related_name="tastes")
    weight = models.DecimalField(max_digits=4, decimal_places=3)
    source = models.CharField(max_length=8, default=SURVEY)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["profile", "tag", "source"], name="books_taste_once")]


class WebLookup(models.Model):
    """One web search for one book, kept so the same book is never searched
    twice, for anyone (Avi, 2026-10-20: very cheap, part of the scan). The
    key is the normalised title and author as read; found or not, it is
    stored. `entry` is the record it produced, if any."""

    key = models.CharField(max_length=300, unique=True)
    title = models.CharField(max_length=300)
    author = models.CharField(max_length=200, blank=True)
    found = models.BooleanField(default=False)
    result = models.JSONField(default=dict, blank=True)
    source_url = models.URLField(max_length=500, blank=True)
    entry = models.ForeignKey(CatalogEntry, on_delete=models.SET_NULL, null=True, blank=True, related_name="web_lookups")
    searches = models.PositiveSmallIntegerField(default=0)
    cost_usd = models.DecimalField(max_digits=8, decimal_places=5, default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]


class EntryEnrichment(models.Model):
    """One enrichment pass over one record, and the mark that it was done,
    so no record is enriched twice (Avi, 2026-10-20). A record with a row is
    left alone; deleting the row (admin) asks for one more pass."""

    DONE, PARTIAL, NOT_FOUND = "done", "partial", "not_found"
    STATUSES = [(DONE, "done"), (PARTIAL, "partly done"), (NOT_FOUND, "not found")]

    entry = models.OneToOneField(CatalogEntry, on_delete=models.CASCADE, related_name="enrichment")
    status = models.CharField(max_length=10, choices=STATUSES, db_index=True)
    filled = models.JSONField(default=list, blank=True, help_text="fields that were blank and are now filled")
    sources = models.JSONField(default=list, blank=True, help_text="where the filled values came from")
    used_web = models.BooleanField(default=False)
    cost_usd = models.DecimalField(max_digits=8, decimal_places=5, default=0)
    note = models.CharField(max_length=300, blank=True)
    enriched_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-enriched_at"]


# ---- rare books and the museum (BK10) ----------------------------------------------------------

class RareReview(models.Model):
    """An owner asks the curators to look at a copy they think is special.
    Sending it is consent for curators to see that copy's photos. Books
    never puts a value on anything (spec 12.8): the outcome is words."""

    PENDING, CONFIRMED, NOT_RARE = "pending", "confirmed", "not_rare"
    STATUSES = [(PENDING, "pending"), (CONFIRMED, "confirmed special"), (NOT_RARE, "not rare")]

    copy = models.OneToOneField(Copy, on_delete=models.CASCADE, related_name="rare_review")
    status = models.CharField(max_length=10, choices=STATUSES, default=PENDING, db_index=True)
    owner_note = models.CharField(max_length=500, blank=True)
    curator_note = models.CharField(max_length=500, blank=True)
    reviewed_by = models.ForeignKey(Profile, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]


class Exhibit(models.Model):
    """A curated exhibition in the museum (data model section 6)."""

    title_he = models.CharField(max_length=160)
    title_en = models.CharField(max_length=160, blank=True)
    text_he = models.TextField(blank=True)
    text_en = models.TextField(blank=True)
    curator = models.ForeignKey(Profile, on_delete=models.SET_NULL, null=True, related_name="exhibits")
    is_published = models.BooleanField(default=False, db_index=True)
    published_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-published_at", "-created_at"]

    def __str__(self):
        return self.title_he

    def title(self, lang):
        return self.title_en if lang == "en" and self.title_en else self.title_he

    def text(self, lang):
        return self.text_en if lang == "en" and self.text_en else self.text_he


class ExhibitItem(models.Model):
    """One copy in an exhibition. Shown only once its owner agreed, and with
    their name only if they chose that (spec BK10: the owner decides)."""

    INVITED, ACCEPTED, DECLINED = "invited", "accepted", "declined"
    CONSENTS = [(INVITED, "invited"), (ACCEPTED, "accepted"), (DECLINED, "declined")]

    exhibit = models.ForeignKey(Exhibit, on_delete=models.CASCADE, related_name="items")
    copy = models.ForeignKey(Copy, on_delete=models.CASCADE, null=True, blank=True, related_name="exhibit_items")
    entry = models.ForeignKey(CatalogEntry, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    note = models.TextField(blank=True, help_text="the curator's words about this item")
    rights_statement = models.CharField(max_length=300, blank=True)
    position = models.PositiveSmallIntegerField(default=0)
    consent = models.CharField(max_length=10, choices=CONSENTS, default=INVITED, db_index=True)
    show_owner_name = models.BooleanField(default=False)
    show_photos = models.BooleanField(default=True)
    answered_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["position", "pk"]
        constraints = [models.UniqueConstraint(fields=["exhibit", "copy"], name="books_exhibit_copy_once")]


# ---- tiers (BK11) -----------------------------------------------------------------------------------

class Coupon(models.Model):
    """A code that grants a tier for some days (Avi, 2026-10-20: "helpavi",
    90 days of the 4.99 tier, while payment is not open)."""

    code = models.CharField(max_length=40, unique=True, help_text="stored lower case")
    tier = models.CharField(max_length=8, choices=Profile.TIERS, default=Profile.PLUS)
    days = models.PositiveSmallIntegerField(default=90)
    is_active = models.BooleanField(default=True)
    max_uses = models.PositiveIntegerField(null=True, blank=True, help_text="empty = no limit")
    uses = models.PositiveIntegerField(default=0)
    expires_at = models.DateTimeField(null=True, blank=True)
    note = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.code


class Subscription(models.Model):
    """A period on a tier (data model section 7): from a coupon now, from a
    payment provider later, or set by hand by staff. The person's tier is
    the highest one in force; Profile.tier stays the hand-set floor."""

    COUPON, MANUAL, PAID = "coupon", "manual", "paid"
    PROVIDERS = [(COUPON, "coupon"), (MANUAL, "set by hand"), (PAID, "payment")]

    profile = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name="subscriptions")
    tier = models.CharField(max_length=8, choices=Profile.TIERS)
    started_at = models.DateTimeField()
    ends_at = models.DateTimeField(db_index=True)
    provider = models.CharField(max_length=8, choices=PROVIDERS, default=COUPON)
    coupon = models.ForeignKey(Coupon, on_delete=models.SET_NULL, null=True, blank=True, related_name="redemptions")
    note = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-ends_at"]
        constraints = [models.UniqueConstraint(fields=["profile", "coupon"], name="books_coupon_once_per_person")]


class ReadingSession(models.Model):
    """One sitting with a book (Avi, 2026-10-20): started with the page you
    are on, timed, ended with the page you reached. The streak counts a day
    once its sessions add up to five minutes; pace is pages over minutes."""

    profile = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name="sessions")
    entry = models.ForeignKey(CatalogEntry, on_delete=models.CASCADE, related_name="sessions")
    copy = models.ForeignKey(Copy, on_delete=models.SET_NULL, null=True, blank=True, related_name="sessions")
    started_at = models.DateTimeField()
    ended_at = models.DateTimeField(null=True, blank=True, db_index=True)
    start_page = models.PositiveIntegerField(default=0)
    end_page = models.PositiveIntegerField(null=True, blank=True)
    seconds = models.PositiveIntegerField(default=0)
    finished_book = models.BooleanField(default=False)
    # Leaving the reading screen pauses the clock (Avi, 2026-10-21).
    paused_at = models.DateTimeField(null=True, blank=True)
    paused_seconds = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["-started_at"]

    @property
    def pages(self):
        if self.end_page is None:
            return 0
        return max(0, self.end_page - self.start_page)

    @property
    def minutes(self):
        return round(self.seconds / 60, 1)


class ReadingNote(models.Model):
    """A thought on a book while reading it (Avi, 2026-10-21), typed or said
    out loud and transcribed. Private to me; notes on a book add up in order."""

    TYPED, VOICE = "typed", "voice"

    profile = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name="reading_notes")
    entry = models.ForeignKey(CatalogEntry, on_delete=models.CASCADE, related_name="notes")
    session = models.ForeignKey(ReadingSession, on_delete=models.SET_NULL, null=True, blank=True, related_name="notes")
    page = models.PositiveIntegerField(null=True, blank=True)
    body = models.TextField(max_length=2000)
    source = models.CharField(max_length=6, choices=[(TYPED, "typed"), (VOICE, "voice")], default=TYPED)
    is_summary = models.BooleanField(default=False)  # written when the book was finished
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["created_at"]
        indexes = [models.Index(fields=["profile", "entry"], name="books_note_profile_entry")]

