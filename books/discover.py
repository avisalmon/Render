"""Discovery (spec BK9): "what should I read next, and who near me has it".
Recommendations stay explainable: every one carries its reason, and there
is no hidden scoring beyond the sums written here.

Taste is per tag, from two places that never overwrite each other: the
survey the person answered (they said it) and what is derived from their own
library, reading log and reviews (they did it). The survey counts double.

"Readers of this also read" counts people, never names them, and shows only
what at least three different people share, so one person's private reading
log can never be read back through it.
"""

from collections import Counter, defaultdict
from decimal import Decimal

from django.db.models import Q

from .hub import blocked_ids, offered_copies
from .models import CatalogEntry, Copy, ProfileTaste, ReadingLog, Review, Tag, Wish

TASTE_KINDS = ("genre", "mood")
SURVEY_WEIGHT = 2
MIN_SHARED = 3


# ---- taste -------------------------------------------------------------------------------

def survey_tags():
    return Tag.objects.filter(kind__in=TASTE_KINDS).order_by("kind", "name_en")


def survey_groups(lang="he"):
    """Every genre under its top-level heading (prose, poetry, non-fiction),
    then the moods: [(heading, [tags])]. A top-level genre is itself a choice."""
    genres = list(Tag.objects.filter(kind="genre").select_related("parent"))
    tops = sorted([t for t in genres if t.parent_id is None], key=lambda t: t.tr(lang))
    groups = []
    for top in tops:
        children = sorted([t for t in genres if t.parent_id == top.pk], key=lambda t: t.tr(lang))
        groups.append((top.tr(lang), [top] + children))
    orphans = [t for t in genres if t.parent_id and t.parent_id not in {x.pk for x in tops}]
    if orphans:
        groups.append(("", orphans))
    moods = sorted(Tag.objects.filter(kind="mood"), key=lambda t: t.tr(lang))
    groups.append((None, moods))
    return groups


def set_survey(profile, likes, dislikes=()):
    """Replace the person's survey answers: liked tags +1, not-for-me -1."""
    likes, dislikes = set(likes), set(dislikes) - set(likes)
    ProfileTaste.objects.filter(profile=profile, source=ProfileTaste.SURVEY).delete()
    for tag in Tag.objects.filter(key__in=likes | dislikes, kind__in=TASTE_KINDS):
        ProfileTaste.objects.create(profile=profile, tag=tag, source=ProfileTaste.SURVEY,
                                    weight=Decimal(1) if tag.key in likes else Decimal(-1))


def _signals(profile):
    """(entry_id, strength) from what the person has done."""
    out = Counter()
    for entry_id in Copy.objects.filter(owner=profile, status__in=Copy.HELD).values_list("entry_id", flat=True):
        out[entry_id] += 0.5
    for entry_id, status in ReadingLog.objects.filter(profile=profile).values_list("entry_id", "status"):
        out[entry_id] += {"read": 1.0, "reading": 0.7, "want": 0.5, "dnf": -1.0}.get(status, 0)
    for entry_id, rating in Review.objects.filter(profile=profile).values_list("entry_id", "rating"):
        out[entry_id] += {5: 1.5, 4: 1.0, 3: 0.0, 2: -1.0, 1: -1.5}.get(rating, 0)
    for entry_id in Wish.objects.filter(profile=profile, entry__isnull=False).values_list("entry_id", flat=True):
        out[entry_id] += 0.5
    return out


def derive(profile):
    """Rebuild the derived taste from the person's own books. Weights are
    normalised to -1..1 so one big shelf does not drown the survey."""
    signals = _signals(profile)
    per_tag = defaultdict(float)
    for entry_id, tag_id in CatalogEntry.tags.through.objects.filter(
            catalogentry_id__in=list(signals), tag__kind__in=TASTE_KINDS).values_list("catalogentry_id", "tag_id"):
        per_tag[tag_id] += signals[entry_id]
    ProfileTaste.objects.filter(profile=profile, source=ProfileTaste.DERIVED).delete()
    top = max((abs(v) for v in per_tag.values()), default=0)
    if not top:
        return {}
    for tag_id, v in per_tag.items():
        w = round(v / top, 3)
        if w:
            ProfileTaste.objects.create(profile=profile, tag_id=tag_id, source=ProfileTaste.DERIVED, weight=Decimal(str(w)))
    return per_tag


def taste(profile):
    """{tag_id: weight}, survey counted double."""
    out = defaultdict(float)
    for tag_id, w, source in ProfileTaste.objects.filter(profile=profile).values_list("tag_id", "weight", "source"):
        out[tag_id] += float(w) * (SURVEY_WEIGHT if source == ProfileTaste.SURVEY else 1)
    return dict(out)


def has_taste(profile):
    return ProfileTaste.objects.filter(profile=profile).exists()


# ---- recommendations -------------------------------------------------------------------------

def _seen(profile):
    """Books the person already has, logged, reviewed or wished for."""
    ids = set(Copy.objects.filter(owner=profile).values_list("entry_id", flat=True))
    ids |= set(ReadingLog.objects.filter(profile=profile).values_list("entry_id", flat=True))
    ids |= set(Review.objects.filter(profile=profile).values_list("entry_id", flat=True))
    return ids


def _loved(profile):
    """Books the person showed they liked, newest first, for "because you liked"."""
    ids = list(Review.objects.filter(profile=profile, rating__gte=4).order_by("-created_at").values_list("entry_id", flat=True))
    ids += [e for e in ReadingLog.objects.filter(profile=profile, status=ReadingLog.READ)
            .values_list("entry_id", flat=True) if e not in ids]
    return CatalogEntry.objects.filter(pk__in=ids[:30]).prefetch_related("tags")


def for_you(profile, limit=24):
    """Records scored by the person's taste, each with its reason: the tags
    that matched, and a book they liked that shares one."""
    weights = taste(profile)
    if not weights:
        return []
    liked = {t for t, w in weights.items() if w > 0}
    if not liked:
        return []
    seen = _seen(profile)
    pool = (CatalogEntry.objects.filter(merged_into__isnull=True, tags__in=liked).exclude(pk__in=seen)
            .distinct().prefetch_related("tags", "creators")[:600])
    loved = list(_loved(profile))
    loved_tags = [(e, {t.pk for t in e.tags.all()}) for e in loved]
    near = {c.entry_id for c, _ in offered_copies(profile, limit=500)}
    recs = []
    for entry in pool:
        tag_ids = {t.pk for t in entry.tags.all() if t.kind in TASTE_KINDS}
        score = sum(weights.get(t, 0) for t in tag_ids)
        if score <= 0:
            continue
        matched = sorted((t for t in entry.tags.all() if weights.get(t.pk, 0) > 0), key=lambda t: -weights[t.pk])[:3]
        because = next((e for e, tags in loved_tags if tags & tag_ids), None)
        if entry.pk in near:
            score += 1  # something you can actually get, nearby
        recs.append({"entry": entry, "score": round(score, 2), "tags": matched, "because": because,
                     "near": entry.pk in near})
    recs.sort(key=lambda r: (-r["score"], r["entry"].title))
    return recs[:limit]


def near_for_you(profile, limit=12):
    """Books offered near me that match my taste, best first."""
    return [r for r in for_you(profile, limit=200) if r["near"]][:limit]


def more_by_author(entry, viewer=None, limit=8):
    creators = list(entry.creators.all())
    if not creators:
        return []
    qs = (CatalogEntry.objects.filter(creators__in=creators, merged_into__isnull=True).exclude(pk=entry.pk)
          .distinct().prefetch_related("creators"))
    if viewer is not None:
        qs = qs.exclude(pk__in=_seen(viewer))
    return list(qs.order_by("-year", "title")[:limit])


def _readers(entry):
    """People who showed they liked or read this book (counted, never named)."""
    ids = set(Review.objects.filter(entry=entry, rating__gte=4).values_list("profile_id", flat=True))
    ids |= set(ReadingLog.objects.filter(entry=entry, status=ReadingLog.READ).values_list("profile_id", flat=True))
    ids |= set(Copy.objects.filter(entry=entry, status__in=Copy.HELD).values_list("owner_id", flat=True))
    return ids


def also_read(entry, viewer=None, limit=8):
    """Books that at least MIN_SHARED of this book's readers also have,
    read or liked. Never names anyone, never shows a pair or a two."""
    readers = _readers(entry)
    if viewer is not None:
        readers -= {viewer.pk} | blocked_ids(viewer)
    if len(readers) < MIN_SHARED:
        return []
    counts = Counter()
    for profile_id, entry_id in Copy.objects.filter(owner_id__in=readers, status__in=Copy.HELD).values_list(
            "owner_id", "entry_id"):
        counts[(entry_id, profile_id)] = 1
    for profile_id, entry_id in ReadingLog.objects.filter(profile_id__in=readers, status=ReadingLog.READ).values_list(
            "profile_id", "entry_id"):
        counts[(entry_id, profile_id)] = 1
    for profile_id, entry_id in Review.objects.filter(profile_id__in=readers, rating__gte=4).values_list(
            "profile_id", "entry_id"):
        counts[(entry_id, profile_id)] = 1
    per_entry = Counter(entry_id for entry_id, _ in counts)
    per_entry.pop(entry.pk, None)
    if viewer is not None:
        for seen in _seen(viewer):
            per_entry.pop(seen, None)
    top = [(eid, n) for eid, n in per_entry.most_common() if n >= MIN_SHARED][:limit]
    entries = CatalogEntry.objects.in_bulk([eid for eid, _ in top])
    return [{"entry": entries[eid], "people": n} for eid, n in top if eid in entries and not entries[eid].merged_into_id]


def available_near(entry, viewer):
    """How many copies of this book are offered near me (or in my circles)."""
    return sum(1 for c, _ in offered_copies(viewer, limit=500) if c.entry_id == entry.pk)


def popular_in_circles(profile, limit=12):
    """What my circles' members hold or read most, that I have not seen."""
    from .models import CircleMember

    mine = CircleMember.objects.filter(profile=profile).values("circle_id")
    members = set(CircleMember.objects.filter(circle_id__in=mine).exclude(profile=profile)
                  .values_list("profile_id", flat=True)) - blocked_ids(profile)
    if not members:
        return []
    pairs = set(Copy.objects.filter(owner_id__in=members, status__in=Copy.HELD).filter(
        Q(visibility=Copy.PUBLIC)).values_list("owner_id", "entry_id"))
    counts = Counter(entry_id for _, entry_id in pairs)
    for seen in _seen(profile):
        counts.pop(seen, None)
    top = [eid for eid, n in counts.most_common(limit) if n >= 2]
    entries = CatalogEntry.objects.in_bulk(top)
    return [{"entry": entries[e], "people": counts[e]} for e in top if e in entries]
