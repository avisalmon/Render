"""Rechecking a filled institution (Epic I, sprint I.2).

Avi, 2026-11-28: "go over all existing institutes and reinvestigate
everything to see that the information that we have is, first of all,
correct... find more interesting professors and researchers for each one."

A recheck file is what a research agent wrote for one institution after
reading what the site holds (every row with its id) against the public web:

- corrections: one field of one existing row, with the value the agent saw
  and the value it proposes, a reason and a source;
- removals: an existing row that is false or cannot be supported;
- additions: new facts, in the shape `research_load.land` already lands.

The rules, on top of the research pass's:

1. a correction applies only while the stored value is still the one the
   agent quoted; if it changed since (an admin edit), it is left alone and
   reported, never overwritten;
2. only plain fields are editable: no ids, slugs, links between rows, files
   or the coverage bookkeeping;
3. a removal hides the row where the table has a flag for it (verified,
   published, active) and deletes it only where it has none, so most
   removals can be undone by the admin;
4. every change and removal is written to the change log under one agent
   run, with the source the agent worked from.
"""
from datetime import date
from decimal import Decimal, InvalidOperation

from django.db import models, transaction

from . import research_load as rl
from .models import (
    ChangeLog,
    Collaboration,
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
from .reread import Counts

AS_OF = date(2026, 11, 28)
LOCKED = {"id", "slug", "institution", "researcher", "unit", "parent", "file", "logo", "photo", "criteria",
          "research_status", "research_as_of", "research_note", "active", "verified", "published", "kind_locked",
          "created_at", "updated_at", "budgeted_by_vatat", "is_leading", "order"}
HIDE = {"verified": False, "published": False, "active": False}


def scopes(inst):
    """model name in the file -> the rows of this institution it may touch."""
    return {
        "institution": Institution.objects.filter(pk=inst.pk),
        "metric": InstitutionMetric.objects.filter(institution=inst),
        "unit": Unit.objects.filter(institution=inst),
        "enrollment": UnitEnrollment.objects.filter(unit__institution=inst),
        "study_program": StudyProgram.objects.filter(institution=inst),
        "section": ProfileSection.objects.filter(institution=inst),
        "document": PublicDocument.objects.filter(institution=inst),
        "timeline": TimelineEvent.objects.filter(institution=inst),
        "center": ResearchCenter.objects.filter(institution=inst),
        "collaboration": Collaboration.objects.filter(institution=inst),
        "distinction": Distinction.objects.filter(institution=inst),
        "researcher": Researcher.objects.filter(institution=inst),
        "researcher_link": ResearcherLink.objects.filter(researcher__institution=inst),
        "researcher_metric": ResearcherMetric.objects.filter(researcher__institution=inst),
        "publication": Publication.objects.filter(researcher__institution=inst),
    }


def clean(field, value):
    """The proposed value in the field's own shape, or raise ValueError."""
    if value is None or value == "":
        if isinstance(field, (models.CharField, models.TextField)):
            return ""
        if field.null:
            return None
        raise ValueError("empty")
    if isinstance(field, models.URLField):
        v = rl.url(value)
        if not v:
            raise ValueError("not a url")
        return v
    if isinstance(field, (models.CharField, models.TextField)):
        v = rl.text(value, getattr(field, "max_length", None))
        if field.choices and v not in dict(field.choices):
            raise ValueError("not a choice")
        return v
    if isinstance(field, models.BooleanField):
        if isinstance(value, bool):
            return value
        raise ValueError("not a boolean")
    if isinstance(field, models.DecimalField):
        try:
            return Decimal(str(value))
        except InvalidOperation as exc:
            raise ValueError("not a number") from exc
    if isinstance(field, models.FloatField):
        return float(value)
    if isinstance(field, (models.IntegerField, models.PositiveSmallIntegerField, models.PositiveIntegerField)):
        v = rl.whole(value)
        if v is None:
            raise ValueError("not a whole number")
        if field.name == "year" or field.name == "founded":
            v = rl.year(v, 1000)
            if v is None:
                raise ValueError("year out of range")
        return v
    if isinstance(field, models.DateField):
        return date.fromisoformat(str(value)[:10])
    raise ValueError("field type not editable")


def same(stored, quoted):
    """The value the agent quoted is the value still stored."""
    if stored in (None, "") and quoted in (None, ""):
        return True
    if isinstance(stored, (int, float, Decimal)) and not isinstance(stored, bool):
        try:
            return Decimal(str(stored)) == Decimal(str(quoted))
        except (InvalidOperation, TypeError):
            return False
    return rl.text(stored) == rl.text(quoted)


def _log(row, field, old, new, reason, run):
    ChangeLog.objects.create(model=f"academia360.{type(row).__name__}", row_id=str(row.pk), field=field,
                             old="" if old is None else str(old)[:20000], new="" if new is None else str(new)[:20000],
                             actor_kind=ChangeLog.AGENT, reason=(reason or "")[:300], run=run)


def _stamp(row, field_name, source_url):
    """Where the row says its facts came from, after a correction."""
    stamp = {}
    names = {f.name for f in type(row)._meta.get_fields()}
    if isinstance(row, Institution) and field_name in ("identity", "tagline"):
        stamp = {"identity_source": rl.source_line(source_url), "identity_as_of": AS_OF}
    else:
        if "source" in names:
            stamp["source"] = rl.source_line(source_url)
        if "as_of" in names:
            stamp["as_of"] = AS_OF
        if "source_url" in names and rl.url(source_url):
            stamp["source_url"] = rl.url(source_url)
    for k, v in stamp.items():
        setattr(row, k, v)
    return list(stamp)


BOOKKEEPING = {"source", "as_of", "source_url", "identity_source", "identity_as_of"}
MOVABLE = {"researcher", "study_program"}  # may move to another unit of the same institution, named


def move(inst, items, run, report):
    """Unit corrections, after the additions landed (the unit may be new).
    The proposed value is a unit's name at this institution, never an id."""
    rows = scopes(inst)
    for c in items:
        where = f"{c.get('model')}#{c.get('id')}.unit"
        row = rows[c["model"]].filter(pk=c.get("id")).first() if str(c.get("id", "")).isdigit() else None
        name = rl.text(c.get("proposed"), 200)
        unit = Unit.objects.filter(institution=inst, name=name).first() if name else None  # empty: no unit is known
        if row is None or (name and unit is None):
            report["rejected"].append(f"{where}: no such row or unit here")
            continue
        old = row.unit
        quoted = str(c.get("current") or "")
        known = {str(old.pk), old.name, report["unit_names"].get(old.pk, "")} if old else {""}
        if quoted not in known:  # by id, by name, or by the name it had before this file renamed it
            report["stale"].append(f"{where}: stored unit differs from the quoted one, left alone")
            continue
        if old == unit:
            continue
        row.unit = unit
        row.save(update_fields=["unit"])
        _log(row, "unit", old.name if old else "", unit.name if unit else "",
             f"{c.get('reason', '')} {rl.url(c.get('source_url', ''))}".strip(), run)
        report["corrected"] += 1


def correct(inst, items, run, report):
    rows = scopes(inst)
    for c in items:
        where = f"{c.get('model')}#{c.get('id')}.{c.get('field')}"
        if c.get("field") == "unit" and c.get("model") in MOVABLE:
            report["moves"].append(c)
            continue
        if c.get("field") in BOOKKEEPING:
            continue  # stamped by the row's own correction, from its source_url
        qs, name = rows.get(c.get("model")), c.get("field") or ""
        row = qs.filter(pk=c.get("id")).first() if qs is not None and str(c.get("id", "")).isdigit() else None
        if row is None:
            report["rejected"].append(f"{where}: no such row here")
            continue
        try:
            field = type(row)._meta.get_field(name)
        except Exception:  # noqa: BLE001 - an unknown field name is a rejection, whatever Django raises
            report["rejected"].append(f"{where}: no such field")
            continue
        if name in LOCKED or field.is_relation or not field.concrete:
            report["rejected"].append(f"{where}: not editable")
            continue
        old = getattr(row, name)
        if not same(old, c.get("current")):
            report["stale"].append(f"{where}: stored value differs from the quoted one, left alone")
            continue
        try:
            new = clean(field, c.get("proposed"))
        except (ValueError, TypeError) as exc:
            report["rejected"].append(f"{where}: {exc}")
            continue
        if old == new:
            continue
        setattr(row, name, new)
        extra = _stamp(row, name, c.get("source_url", ""))
        row.save(update_fields=[name, *extra])
        _log(row, name, old, new, f"{c.get('reason', '')} {rl.url(c.get('source_url', ''))}".strip(), run)
        report["corrected"] += 1


def remove(inst, items, run, report):
    rows = scopes(inst)
    for r in items:
        where = f"{r.get('model')}#{r.get('id')}"
        if r.get("model") == "institution":
            report["rejected"].append(f"{where}: an institution is never removed here")
            continue
        qs = rows.get(r.get("model"))
        row = qs.filter(pk=r.get("id")).first() if qs is not None and str(r.get("id", "")).isdigit() else None
        if row is None:
            report["rejected"].append(f"{where}: no such row here")
            continue
        reason = f"{r.get('reason', '')} {rl.url(r.get('source_url', ''))}".strip()
        flag = next((f for f in HIDE if f in {x.name for x in type(row)._meta.concrete_fields}), None)
        if flag:
            if getattr(row, flag) is False:
                continue
            setattr(row, flag, False)
            row.save(update_fields=[flag])
            _log(row, flag, True, False, reason, run)
            report["hidden"] += 1
        else:
            _log(row, "", str(row), "", reason, run)
            row.delete()
            report["deleted"] += 1


def apply(inst, data, run=None, counts=None):
    """Corrections, additions, unit moves, then removals, in one transaction.
    Returns a report dict; counts collects the additions."""
    counts = counts if counts is not None else Counts()
    report = {"corrected": 0, "hidden": 0, "deleted": 0, "stale": [], "rejected": [], "moves": []}
    with transaction.atomic():
        report["unit_names"] = dict(Unit.objects.filter(institution=inst).values_list("pk", "name"))
        correct(inst, data.get("corrections") or [], run, report)
        adds = dict(data.get("additions") or {})
        adds.setdefault("gaps", data.get("gaps") or "")
        before = sum(v[0] for v in counts.values())
        rl.land(inst, adds, counts)
        report["added"] = sum(v[0] for v in counts.values()) - before
        move(inst, report.pop("moves"), run, report)
        report.pop("unit_names")
        remove(inst, data.get("removals") or [], run, report)  # last: a removed unit's people have moved by now
        mark_rechecked(inst, data, report)
    return report


def mark_rechecked(inst, data, report):
    inst.refresh_from_db()
    inst.research_status = Institution.RESEARCH_RECHECKED
    inst.research_as_of = AS_OF
    note = (f"בדיקה חוזרת, {AS_OF:%d.%m.%Y}: {report['corrected']} תיקונים, {report['hidden'] + report['deleted']} "
            f"הוסרו, {report.get('added', 0)} נוספו.")
    if data.get("gaps"):
        note += " חסר: " + rl.text(data["gaps"], 1500)
    inst.research_note = note
    inst.save(update_fields=["research_status", "research_as_of", "research_note"])
