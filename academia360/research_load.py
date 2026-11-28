"""Landing a researched institution (Epic I, the first research pass).

Avi, 2026-11-27: "run a deep research of every empty university and fill up
the information as we have in the other filled-in institutes... make it rich,
correct and interesting."

The research itself happens outside the app (a chat agent reads the public
web and writes one JSON file per institution, every fact with the URL it was
read from). This module lands such a file, under the rules of the reference
reading (`reread`):

1. nothing is invented here: a key the file leaves empty stays empty;
2. what is already filled is never overwritten, only empty fields are filled
   and only missing rows are added, so a second run changes nothing;
3. every row carries the same source line and date, so the page says where a
   fact came from and the coverage list can tell this pass from the reference;
4. a value that does not fit the model (an unknown kind, a URL that is not
   http, a year out of range) is dropped, never guessed into shape.
"""
import json
import re
from datetime import date
from decimal import Decimal, InvalidOperation
from urllib.parse import urlparse

from django.db import transaction

from .models import (
    Collaboration,
    Criterion,
    Distinction,
    Institution,
    InstitutionMetric,
    ProfileSection,
    Publication,
    PublicDocument,
    ResearchCenter,
    Researcher,
    ResearcherLink,
    ResearcherMetric,
    StudyProgram,
    TimelineEvent,
    Unit,
    UnitEnrollment,
)
from .reread import Counts, _fill, _match_researcher, _slug

SOURCE = "מחקר ציבורי, נובמבר 2026"
AS_OF = date(2026, 11, 27)
METRIC_KEY = re.compile(r"^[a-z][a-z0-9_]{1,59}$")


# ------------------------------------------------------------------ cleaning

def text(value, limit=None):
    """Plain text the way the site writes it: no em or en dashes, no stray
    whitespace. Avi's rule for anything shown."""
    if value is None:
        return ""
    s = str(value).replace("—", " - ").replace("–", "-").replace(" ", " ")
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r" +([,.;:])", r"\1", s).strip()
    return s[:limit] if limit else s


def url(value):
    s = (value or "").strip()
    p = urlparse(s)
    if p.scheme in ("http", "https") and p.netloc and len(s) <= 200:
        return s
    return ""


def year(value, low=1800, high=2027):
    try:
        y = int(value)
    except (TypeError, ValueError):
        return None
    return y if low <= y <= high else None


def number(value):
    try:
        n = Decimal(str(value).replace(",", ""))
    except (InvalidOperation, TypeError, ValueError):
        return None
    return n if n >= 0 else None


def whole(value):
    n = number(value)
    return int(n) if n is not None else None


def choice(value, choices, default=None):
    keys = {k for k, _ in choices}
    return value if value in keys else default


def domain(u):
    return urlparse(u).netloc.removeprefix("www.") if u else ""


def source_line(u=""):
    d = domain(url(u))
    return (f"{SOURCE} · {d}" if d else SOURCE)[:200]


# ------------------------------------------------------------------- landing

def land(inst, data, counts=None):
    """Everything in one research file for one institution. Returns counts."""
    counts = counts if counts is not None else Counts()
    with transaction.atomic():
        _institution(inst, data.get("institution") or {}, counts)
        _metrics(inst, data.get("metrics") or [], counts)
        units = _units(inst, data.get("units") or [], counts)
        _programs(inst, data.get("study_programs") or [], units, counts)
        _sections(inst, data.get("sections") or [], counts)
        _documents(inst, data.get("documents") or [], counts)
        _timeline(inst, data.get("timeline") or [], counts)
        _centers(inst, data.get("centers") or [], counts)
        _collaborations(inst, data.get("collaborations") or [], counts)
        people = _researchers(inst, data.get("researchers") or [], units, counts)
        _distinctions(inst, data.get("distinctions") or [], people, counts)
        mark_researched(inst, data.get("gaps") or "")
    return counts


def _institution(inst, d, counts):
    ident = text(d.get("identity"))
    _fill(inst, counts, "institution", name_en=text(d.get("name_en"), 200),
          short_name_he=text(d.get("short_name_he"), 80), website=url(d.get("website")),
          founded=year(d.get("founded")), founder=text(d.get("founder"), 200), city=text(d.get("city"), 80),
          lat=d.get("lat") if isinstance(d.get("lat"), (int, float)) else None,
          lng=d.get("lng") if isinstance(d.get("lng"), (int, float)) else None,
          tagline=text(d.get("tagline"), 200), identity=ident)
    if ident and inst.identity == ident and not inst.identity_source:
        inst.identity_source = source_line(d.get("identity_source_url") or d.get("website"))
        inst.identity_as_of = AS_OF
        inst.save(update_fields=["identity_source", "identity_as_of"])


def _metrics(inst, rows, counts):
    for m in rows:
        key, value = (m.get("key") or "").strip(), number(m.get("value"))
        if not METRIC_KEY.match(key) or value is None:
            counts.hit("dropped", created=False)
            continue
        y = year(m.get("year"), 1950)
        if inst.metrics.filter(key=key, year=y).exists():
            counts.hit("metrics", created=False)
            continue
        InstitutionMetric.objects.create(
            institution=inst, key=key, year=y, value=value, unit=text(m.get("unit"), 30) or "count",
            source=(text(m.get("source"), 150) + " · " + SOURCE if m.get("source") else SOURCE)[:200],
            source_url=url(m.get("source_url")), as_of=AS_OF, verified=True)
        counts.hit("metrics")


def _units(inst, rows, counts):
    """name -> Unit, created when missing; students per unit as an
    enrollment row when the file has a number."""
    out = {}
    order = inst.units.count()
    for u in rows:
        name = text(u.get("name"), 200)
        if not name:
            continue
        unit = inst.units.filter(name=name).first()
        if unit is None:
            order += 1
            unit = Unit.objects.create(institution=inst, name=name, order=order,
                                       kind=choice(u.get("kind"), Unit.KINDS, Unit.FACULTY), website=url(u.get("website")))
            counts.hit("units")
        else:
            counts.hit("units", created=False)
            _fill(unit, counts, "units", website=url(u.get("website")))
        out[name] = unit
        students = whole(u.get("students"))
        if students and not unit.enrollments.exists():
            pct = number(u.get("share_pct"))
            UnitEnrollment.objects.create(
                unit=unit, year=year(u.get("students_year"), 1990), students=students,
                approximate=bool(u.get("approximate")), share_pct=pct if pct is not None and pct <= 100 else None,
                source=source_line(u.get("source_url")), as_of=AS_OF, verified=True)
            counts.hit("unit enrollment")
    return out


def _programs(inst, rows, units, counts):
    for p in rows:
        name = text(p.get("name"), 200)
        if not name:
            continue
        level = choice(p.get("level"), StudyProgram.LEVELS, StudyProgram.UNDERGRAD)
        if inst.study_programs.filter(name=name, level=level).exists():
            counts.hit("study programs", created=False)
            continue
        StudyProgram.objects.create(institution=inst, name=name, level=level, degree=text(p.get("degree"), 20),
                                    field=choice(p.get("field"), StudyProgram.FIELDS, ""),
                                    unit=units.get(text(p.get("unit"), 200)))
        counts.hit("study programs")


def _sections(inst, rows, counts):
    order = inst.sections.count()
    for s in rows:
        title, body = text(s.get("title"), 200), text(s.get("body"), 6000)
        if not title or not body:
            continue
        if inst.sections.filter(title=title).exists():
            counts.hit("sections", created=False)
            continue
        order += 1
        ProfileSection.objects.create(institution=inst, kind=choice(s.get("kind"), ProfileSection.KINDS, "other"),
                                      title=title, body=body, order=order, source=source_line(s.get("source_url")),
                                      as_of=AS_OF)
        counts.hit("sections")


def _documents(inst, rows, counts):
    criteria = {c.slug: c for c in Criterion.objects.all()}
    order = inst.public_documents.count()
    for d in rows:
        title, link = text(d.get("title"), 300), url(d.get("url"))
        if not title or not link:
            counts.hit("dropped", created=False)
            continue
        if inst.public_documents.filter(url=link).exists():
            counts.hit("documents", created=False)
            continue
        order += 1
        py = year(d.get("published_year"), 1950)
        doc = PublicDocument.objects.create(
            institution=inst, title=title, url=link, kind=choice(d.get("kind"), PublicDocument.KINDS, "other"),
            summary=text(d.get("summary"), 2000), published_at=date(py, 1, 1) if py else None,
            source=source_line(link), as_of=AS_OF, verified=True, order=order)
        doc.criteria.set([criteria[c] for c in d.get("criteria") or [] if c in criteria])
        counts.hit("documents")


def _timeline(inst, rows, counts):
    for t in rows:
        y, line = year(t.get("year"), 1000), text(t.get("text"), 300)
        if not y or not line:
            continue
        _, made = TimelineEvent.objects.get_or_create(institution=inst, year=y, text=line)
        counts.hit("timeline", made)


def _centers(inst, rows, counts):
    order = inst.centers.count()
    for c in rows:
        name = text(c.get("name"), 200)
        if not name:
            continue
        if inst.centers.filter(name=name).exists():
            counts.hit("centers", created=False)
            continue
        order += 1
        ResearchCenter.objects.create(institution=inst, name=name, full_name=text(c.get("full_name"), 300),
                                      founded=year(c.get("founded")), focus=text(c.get("focus")), url=url(c.get("url")),
                                      order=order)
        counts.hit("centers")


def _collaborations(inst, rows, counts):
    for c in rows:
        partner, kind = text(c.get("partner"), 200), choice(c.get("kind"), Collaboration.KINDS)
        if not partner or not kind:
            continue
        _, made = Collaboration.objects.get_or_create(institution=inst, partner=partner, kind=kind,
                                                      defaults=dict(description=text(c.get("description"))))
        counts.hit("collaborations", made)


def _researchers(inst, rows, units, counts):
    """name_he -> Researcher. Matches a person the reference already brought
    by name before creating one."""
    out = {}
    for p in rows:
        name_he, name_en = text(p.get("name_he"), 160), text(p.get("name_en"), 160)
        if not (name_he or name_en):
            continue
        title = text(p.get("title"), 80)
        row = _match_researcher(inst, {"title": title, "name_he": name_he, "name_en": name_en})
        if row is None:
            row = Researcher.objects.create(institution=inst, slug=_slug(inst, {"name_he": name_he, "name_en": name_en}),
                                            name_he=name_he or name_en, name_en=name_en, title=title, is_leading=True)
            counts.hit("researchers")
        else:
            counts.hit("researchers", created=False)
        _fill(row, counts, "researchers", title=title, name_en=name_en, position=text(p.get("position"), 160),
              areas=text(p.get("areas"), 300), focus=text(p.get("focus")), bio=text(p.get("bio")),
              unit=units.get(text(p.get("unit"), 200)))
        kind = choice(p.get("kind"), Researcher.KINDS)
        if row.kind == Researcher.OTHER and kind and kind != Researcher.OTHER:  # "other" is the default, not a fact
            row.kind = kind
            row.save(update_fields=["kind"])
        out[name_he] = row
        try:  # the day the metrics were read, when the file says it
            as_of = date.fromisoformat(str(p.get("metrics_as_of") or "")[:10])
        except ValueError:
            as_of = AS_OF
        oa = (p.get("openalex_id") or "").strip()
        for metric, value in (("h_index", whole(p.get("h_index"))), ("citations", whole(p.get("citations")))):
            if value is None or row.metrics.filter(metric=metric, as_of=as_of).exists():
                continue
            ResearcherMetric.objects.create(researcher=row, metric=metric, value=value, as_of=as_of,
                                            source=f"OpenAlex{' ' + oa.rsplit('/', 1)[-1] if oa else ''}"[:120])
            counts.hit("researcher metrics")
        links = list(p.get("links") or [])
        if oa and not any("openalex.org" in (lk.get("url") or "") for lk in links):
            links.append({"kind": "other", "url": oa if oa.startswith("http") else f"https://openalex.org/{oa}"})
        for lk in links:
            link = url(lk.get("url"))
            if not link or "scholar.google" in link:
                continue
            _, made = ResearcherLink.objects.get_or_create(
                researcher=row, url=link,
                defaults=dict(kind=choice(lk.get("kind"), ResearcherLink.KINDS, "other"), verified_at=AS_OF))
            counts.hit("researcher links", made)
        for pub in p.get("publications") or []:
            ptitle = text(pub.get("title"), 300)
            if not ptitle:
                continue
            _, made = Publication.objects.get_or_create(
                researcher=row, title=ptitle,
                defaults=dict(venue=text(pub.get("venue"), 200), year=year(pub.get("year"), 1900),
                              citations=whole(pub.get("citations")), url=url(pub.get("url"))))
            counts.hit("publications", made)
        for prize in p.get("prizes") or []:
            _distinction(inst, prize, row, counts)
    return out


def _distinction(inst, d, researcher, counts):
    kind = choice(d.get("kind"), Distinction.KINDS, "other")
    title, y = text(d.get("title"), 300), year(d.get("year"), 1900)
    if not title:
        return
    if Distinction.objects.filter(institution=inst, researcher=researcher, kind=kind, year=y).exists():
        counts.hit("distinctions", created=False)
        return
    Distinction.objects.create(institution=inst, researcher=researcher, kind=kind, title=title, year=y,
                               url=url(d.get("url")), source=source_line(d.get("url")), as_of=AS_OF, verified=True)
    counts.hit("distinctions")


def _distinctions(inst, rows, people, counts):
    for d in rows:
        who = people.get(text(d.get("researcher_name_he"), 160))
        if who is None and d.get("researcher_name_he"):
            who = _match_researcher(inst, {"title": "", "name_he": text(d["researcher_name_he"]), "name_en": ""})
        _distinction(inst, d, who, counts)


def mark_researched(inst, gaps=""):
    """The coverage list: this institution was filled by the public research
    pass. A 'rechecked' stays rechecked."""
    if inst.research_status == Institution.RESEARCH_RECHECKED:
        return
    inst.research_status = Institution.RESEARCH_IMPORTED
    inst.research_as_of = AS_OF
    note = f"{SOURCE}: מחקר רשת לכל מוסד, כל עובדה עם הקישור שממנו נקראה."
    if gaps:
        note += " חסר: " + text(gaps, 1500)
    if not inst.research_note:
        inst.research_note = note
    inst.save(update_fields=["research_status", "research_as_of", "research_note"])


def load_file(path):
    with open(path, encoding="utf-8-sig") as f:
        return json.load(f)
