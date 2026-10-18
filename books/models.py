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
