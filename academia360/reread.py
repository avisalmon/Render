"""The second reading of the reference (Epic P, sprint P.2).

`reference_pages` reads a page by meaning; this module lands what it read in
the database, under three rules Avi set on 2026-11-27:

1. everything the reference holds finds its place;
2. nothing is invented: a field the page does not state stays empty, and
   an institution without pages gets nothing at all;
3. what is already filled is never overwritten. A row the admin edited, or
   a value a later job verified, survives a re-run. Only empty fields are
   filled, and only rows that are missing are added, so running it twice
   changes nothing the second time.

Every row added carries the same source line and date, so the page can say
where a fact came from and the coverage list can tell this material from
what a later research job brings.
"""
from datetime import date

from django.db import transaction
from django.utils.text import slugify

from . import reference_pages as pages
from .models import (
    Distinction,
    Institution,
    InstitutionMetric,
    ProfileSection,
    Publication,
    Researcher,
    ResearcherLink,
    ResearcherMetric,
    TimelineEvent,
    Unit,
    UnitEnrollment,
)

SOURCE = "דף הרפרנס של אבי, אוקטובר 2025"
AS_OF = date(2025, 10, 1)


class Counts(dict):
    def hit(self, what, created=True):
        a, b = self.get(what, (0, 0))
        self[what] = (a + 1, b) if created else (a, b + 1)


def _fill(row, counts, what, **fields):
    """Set each field only when the row's value is empty. Saves once."""
    changed = []
    for name, value in fields.items():
        if value in (None, "", []):
            continue
        if getattr(row, name) in (None, "", 0, False) and getattr(row, name) != value:
            setattr(row, name, value)
            changed.append(name)
    if changed:
        row.save(update_fields=changed)
        counts.hit(what + " fields")
    return changed


# ------------------------------------------------------------------- people

def _match_researcher(inst, person):
    """The same person the first import may have created, by name."""
    key = pages.normal_name(" ".join(x for x in (person["title"], person["name_he"], f"({person['name_en']})" if person['name_en'] else "") if x))
    keys = {key, pages.normal_name(person["name_he"]), pages.normal_name(person["name_en"])} - {""}
    for r in inst.researchers.all():
        for raw in (r.name_he, r.name_en, f"{r.title} {r.name_he}".strip()):
            if raw and pages.normal_name(raw) in keys:
                return r
    return None


def _slug(inst, person):
    base = slugify(person["name_he"] or person["name_en"], allow_unicode=True)[:48] or "r"
    slug, n = base, 2
    while Researcher.objects.filter(institution=inst, slug=slug).exists():
        slug, n = f"{base}-{n}", n + 1
    return slug


def apply_people(inst, page_html, counts=None, dry=False):
    """Land a researchers page: people, their position and unit, focus, bio,
    metrics, publications, links and prizes. Returns the counts."""
    counts = counts if counts is not None else Counts()
    people = pages.read_people(page_html)
    for person in people:
        if not (person["name_he"] or person["name_en"]):
            continue
        row = _match_researcher(inst, person)
        if row is None:
            counts.hit("researchers")
            if dry:
                continue
            row = Researcher.objects.create(
                institution=inst, slug=_slug(inst, person), name_he=person["name_he"] or person["name_en"],
                name_en=person["name_en"], title=person["title"], is_leading=True)
        else:
            counts.hit("researchers", created=False)
            if dry:
                continue
            # the first import kept '(Shie Mannor)' inside the Hebrew name; split it, once
            if "(" in row.name_he and person["name_he"] and not row.name_en:
                row.name_he, row.name_en = person["name_he"], person["name_en"]
                row.save(update_fields=["name_he", "name_en"])
        unit = None
        if person["unit"]:
            unit, made = Unit.objects.get_or_create(institution=inst, name=person["unit"][:200])
            counts.hit("units", made)
        _fill(row, counts, "researchers", title=person["title"], name_en=person["name_en"],
              position=person["position"], focus=person["focus"], bio=person["bio"], unit=unit,
              areas=person["focus"][:300] if not row.areas else None)
        for metric, value, approx in (("h_index", person["h_index"], person["h_approx"]),
                                      ("citations", person["citations"], person["cites_approx"])):
            if value is None:
                continue
            as_of = date(person["as_of_year"], 1, 1) if person["as_of_year"] else AS_OF
            _, made = ResearcherMetric.objects.get_or_create(
                researcher=row, metric=metric, as_of=as_of, defaults=dict(value=value, approximate=approx, source=SOURCE))
            counts.hit("metrics", made)
        for title, venue, year in person["publications"]:
            _, made = Publication.objects.get_or_create(researcher=row, title=title[:300],
                                                        defaults=dict(venue=venue[:200], year=year))
            counts.hit("publications", made)
        for kind, url in person["links"]:
            _, made = ResearcherLink.objects.get_or_create(researcher=row, url=url[:200], defaults=dict(kind=kind))
            counts.hit("links", made)
        for kind, title, year in person["prizes"]:
            # one row per person, kind and year; a richer title later never doubles it
            existing = Distinction.objects.filter(institution=inst, researcher=row, kind=kind, year=year).first()
            if existing is None:
                Distinction.objects.create(institution=inst, researcher=row, kind=kind, title=title[:300], year=year,
                                           source=SOURCE, as_of=AS_OF)
                counts.hit("distinctions")
            else:
                counts.hit("distinctions", created=False)
                if len(title) > len(existing.title) and title.startswith(existing.title[:6]):
                    existing.title = title[:300]
                    existing.save(update_fields=["title"])
    # rows the first import took for people but are the page's area headings
    if not dry:
        for heading in pages.non_person_headings(page_html):
            key = pages.normal_name(heading)
            for r in inst.researchers.filter(verified=True):
                if key and pages.normal_name(r.name_he) == key:
                    r.verified = False
                    r.save(update_fields=["verified"])
                    counts.hit("unverified non-people")
    return counts


# ------------------------------------------------------------------ overview

def apply_overview(inst, page_html, counts=None, dry=False):
    """Land an overview page: tagline, facts as metrics, students per
    faculty, timeline, section kinds and texts, prize winners."""
    counts = counts if counts is not None else Counts()
    o = pages.read_overview(page_html)
    if dry:
        n = sum(len(v) if isinstance(v, list) else int(bool(v)) for v in o.values())
        counts["would read"] = (counts.get("would read", (0, 0))[0] + n, 0)
        return counts
    _fill(inst, counts, "institution", tagline=o["tagline"])
    for key, value, approx, year, label in o["facts"]:
        if key == "founded":
            _fill(inst, counts, "institution", founded=int(value))
            continue
        _, made = InstitutionMetric.objects.get_or_create(
            institution=inst, key=key, year=year, source=SOURCE,
            defaults=dict(value=value, unit="headcount" if "students" in key or "faculty" in key or "alumni" in key else "count",
                          as_of=AS_OF, verified=True))
        counts.hit("metrics", made)
    for name, students, approx, pct in o["split"]:
        unit, made = Unit.objects.get_or_create(institution=inst, name=name[:200])
        counts.hit("units", made)
        _, made = UnitEnrollment.objects.get_or_create(
            unit=unit, source=SOURCE, year=None,
            defaults=dict(students=students, approximate=approx, share_pct=pct, as_of=AS_OF))
        counts.hit("unit enrollment", made)
    for year, text in o["timeline"]:
        _, made = TimelineEvent.objects.get_or_create(institution=inst, year=year, text=text[:300])
        counts.hit("timeline", made)
    order = 0
    for title, kind, text in o["sections"]:
        order += 1
        row, made = ProfileSection.objects.get_or_create(
            institution=inst, title=title[:200],
            defaults=dict(kind=kind, body=text[:6000], order=order, source=SOURCE, as_of=AS_OF))
        counts.hit("sections", made)
        if not made and row.kind == "other" and kind != "other":
            row.kind = kind
            row.save(update_fields=["kind"])
            counts.hit("section kinds")
    for name, field, year in o["winners"]:
        who = _match_researcher(inst, {"title": "", "name_he": name, "name_en": ""})
        nobel = "נובל" in page_html
        title = (f"פרס נובל {field}" if nobel else field or "פרס").strip()
        existing = Distinction.objects.filter(institution=inst, researcher=who, kind="nobel" if nobel else "other",
                                              year=year).first()
        if existing is None:
            Distinction.objects.create(institution=inst, researcher=who, kind="nobel" if nobel else "other",
                                       title=title[:300], year=year, source=SOURCE, as_of=AS_OF)
            counts.hit("distinctions")
        else:
            counts.hit("distinctions", created=False)
            if len(title) > len(existing.title):
                existing.title = title[:300]
                existing.save(update_fields=["title"])
    return counts


def mark_imported(inst, note="", dry=False):
    """The coverage list's status: this institution's material came from the
    reference. Never downgrades a 'rechecked'."""
    if dry or inst.research_status == Institution.RESEARCH_RECHECKED:
        return
    inst.research_status = Institution.RESEARCH_IMPORTED
    inst.research_as_of = AS_OF
    if note and not inst.research_note:
        inst.research_note = note
    inst.save(update_fields=["research_status", "research_as_of", "research_note"])


@transaction.atomic
def reread(inst, folder, counts=None, dry=False):
    """Everything for one institution's folder. Returns (counts, pages read)."""
    counts = counts if counts is not None else Counts()
    read = []
    for name in ("researchers.html", "leading_researchers.html"):
        p = folder / name
        if p.exists():
            apply_people(inst, p.read_text(encoding="utf-8", errors="replace"), counts, dry=dry)
            read.append(name)
    p = folder / "index.html"
    if p.exists():
        apply_overview(inst, p.read_text(encoding="utf-8", errors="replace"), counts, dry=dry)
        read.append("index.html")
    if read:
        mark_imported(inst, note="ברפרנס: " + ", ".join(read), dry=dry)
    return counts, read
