"""Academia360 sprint I.2: rechecking every filled institution

Avi, 2026-11-28: go over every institution again, check that what we have
is correct, enrich it, and find more significant researchers. An agent reads
what the site holds (every row with its id) against the public web and
writes corrections, removals and additions. The recheck applies them:

- a correction lands only while the stored value is the one the agent
  quoted, so an admin edit made since is never overwritten;
- plain fields only: ids, slugs, links between rows and bookkeeping are not
  the agent's to change, and another institution's row is out of reach;
- a removal hides where the table can hide, deletes only where it cannot;
- every change is in the change log under one run, and the institution
  reads "rechecked" with a note of what happened.
"""
import json

import pytest
from django.core.management import call_command

from academia360 import research_recheck
from academia360.models import (
    AgentRun,
    ChangeLog,
    Institution,
    ProfileSection,
    Researcher,
    TimelineEvent,
)

pytestmark = pytest.mark.django_db


@pytest.fixture
def world(db):
    inst = Institution.objects.create(slug="tau", name_he="אוניברסיטת תל אביב", kind=Institution.UNIVERSITY,
                                      founded=1965, identity="טקסט מתורגם במכונה.")
    other = Institution.objects.create(slug="other", name_he="אחרת", kind=Institution.UNIVERSITY)
    sec = ProfileSection.objects.create(institution=inst, kind="overview", title="סקירה", body="ישן")
    gone = Researcher.objects.create(institution=inst, slug="gone", name_he="עבר למקום אחר", title="פרופ׳")
    stays = Researcher.objects.create(institution=inst, slug="stays", name_he="דנה לוי", title="ד״ר", position="מרצה")
    tl = TimelineEvent.objects.create(institution=inst, year=2030, text="אירוע מומצא")
    foreign = ProfileSection.objects.create(institution=other, kind="overview", title="זר", body="לא לגעת")
    return {"inst": inst, "sec": sec, "gone": gone, "stays": stays, "tl": tl, "foreign": foreign}


def recheck(w):
    return {
        "slug": "tau",
        "corrections": [
            {"model": "institution", "id": w["inst"].pk, "field": "founded", "current": 1965, "proposed": 1956,
             "reason": "שנת ייסוד", "source_url": "https://www.tau.ac.il/about"},
            {"model": "institution", "id": w["inst"].pk, "field": "identity", "current": "טקסט מתורגם במכונה.",
             "proposed": "אוניברסיטת תל אביב — הגדולה בישראל.", "source_url": "https://www.tau.ac.il/about"},
            {"model": "section", "id": w["sec"].pk, "field": "body", "current": "ישן", "proposed": "**חדש**"},
            {"model": "researcher", "id": w["stays"].pk, "field": "position", "current": "מרצה בכירה",
             "proposed": "פרופסור"},  # the agent misquoted: left alone
            {"model": "researcher", "id": w["stays"].pk, "field": "slug", "current": "stays", "proposed": "x"},
            {"model": "section", "id": w["foreign"].pk, "field": "body", "current": "לא לגעת", "proposed": "נגעתי"},
            {"model": "researcher", "id": w["stays"].pk, "field": "nonsense", "current": "", "proposed": "x"},
        ],
        "removals": [
            {"model": "researcher", "id": w["gone"].pk, "reason": "עבר לאוניברסיטה אחרת"},
            {"model": "timeline", "id": w["tl"].pk, "reason": "שנה עתידית"},
            {"model": "institution", "id": w["inst"].pk, "reason": "never"},
        ],
        "additions": {
            "researchers": [{"name_he": "עדה יונת", "name_en": "Ada Yonath", "title": "פרופ׳", "kind": "other",
                             "focus": "מבנה הריבוזום",
                             "prizes": [{"kind": "nobel", "title": "פרס נובל בכימיה", "year": 2009}]},
                            {"name_he": "דנה לוי", "prizes": [{"kind": "other", "title": "פרס הוראה", "year": 2024}]}],
            "timeline": [{"year": 1956, "text": "האוניברסיטה נוסדה"}],
        },
        "gaps": "אין פיצול סטודנטים",
        "sources": ["https://www.tau.ac.il/about"],
    }


def test_a_recheck_corrects_what_was_quoted_and_nothing_else(world):
    report = research_recheck.apply(world["inst"], recheck(world))
    inst = Institution.objects.get(pk=world["inst"].pk)
    assert inst.founded == 1956
    assert "—" not in inst.identity and inst.identity_source.endswith("tau.ac.il")
    assert ProfileSection.objects.get(pk=world["sec"].pk).body == "**חדש**"
    stays = Researcher.objects.get(pk=world["stays"].pk)
    assert stays.position == "מרצה" and stays.slug == "stays"  # misquoted and locked: untouched
    assert ProfileSection.objects.get(pk=world["foreign"].pk).body == "לא לגעת"
    assert report["corrected"] == 3 and len(report["stale"]) == 1 and len(report["rejected"]) == 4


def test_a_removal_hides_where_it_can_and_the_additions_land(world):
    report = research_recheck.apply(world["inst"], recheck(world))
    assert Researcher.objects.get(pk=world["gone"].pk).verified is False
    assert not TimelineEvent.objects.filter(pk=world["tl"].pk).exists()
    assert Institution.objects.filter(pk=world["inst"].pk, active=True).exists()
    assert report["hidden"] == 1 and report["deleted"] == 1
    inst = Institution.objects.get(pk=world["inst"].pk)
    yonath = inst.researchers.get(name_en="Ada Yonath")
    assert yonath.distinctions.get().kind == "nobel"
    assert Researcher.objects.get(pk=world["stays"].pk).distinctions.get().title == "פרס הוראה"  # matched by name
    assert list(inst.timeline.values_list("year", flat=True)) == [1956]
    assert inst.research_status == Institution.RESEARCH_RECHECKED and "אין פיצול" in inst.research_note


def test_every_change_is_logged_under_one_run_and_a_dry_run_leaves_nothing(world, tmp_path):
    path = tmp_path / "tau.json"
    path.write_text(json.dumps(recheck(world), ensure_ascii=False), encoding="utf-8")
    call_command("recheck_research", str(path), "--dry-run")
    assert Institution.objects.get(pk=world["inst"].pk).founded == 1965 and not AgentRun.objects.exists()
    call_command("recheck_research", str(path))
    run = AgentRun.objects.get()
    logged = ChangeLog.objects.filter(run=run)
    assert logged.count() == 5 and all(c.actor_kind == ChangeLog.AGENT for c in logged)
    assert logged.get(field="founded").old == "1965" and "tau.ac.il" in logged.get(field="founded").reason
    call_command("recheck_research", str(path))  # a second run finds every quote stale: nothing changes
    assert Institution.objects.get(pk=world["inst"].pk).founded == 1956
    assert ChangeLog.objects.filter(run=AgentRun.objects.order_by("-pk").first()).count() == 0


def test_a_person_moves_to_a_named_unit_of_the_same_institution_before_a_wrong_unit_is_removed(world):
    from academia360.models import Unit

    inst, stays = world["inst"], world["stays"]
    rank = Unit.objects.create(institution=inst, name="פרופסור חבר")  # an academic rank imported as a unit
    stays.unit = rank
    stays.save()
    foreign = Unit.objects.create(institution=Institution.objects.get(slug="other"), name="מדעי המחשב")
    data = {"slug": "tau", "corrections": [
        {"model": "researcher", "id": stays.pk, "field": "unit", "current": rank.pk, "proposed": "מדעי המחשב"}],
        "removals": [{"model": "unit", "id": rank.pk, "reason": "דרגה, לא יחידה"}],
        "additions": {"units": [{"name": "מדעי המחשב", "kind": "school"}]}}
    report = research_recheck.apply(inst, data)
    stays.refresh_from_db()
    assert stays.unit.name == "מדעי המחשב" and stays.unit.institution == inst and stays.unit != foreign
    assert not Unit.objects.filter(pk=rank.pk).exists() and report["corrected"] == 1


def test_a_prize_or_numbers_for_someone_not_found_never_make_a_new_person(world):
    from academia360 import research_load
    from academia360.models import ResearcherLink

    inst, stays = world["inst"], world["stays"]
    ResearcherLink.objects.create(researcher=stays, url="https://openalex.org/A5000000001", kind="other")
    before = Researcher.objects.count()
    research_load.land(inst, {"researchers": [
        {"name_he": "דנה לוי-כהן", "prizes": [{"kind": "erc", "title": "ERC Starting Grant", "year": 2024}]},  # misspelt
        {"name_he": "Dana Levy", "name_en": "Dana Levy", "openalex_id": "A5000000001", "h_index": 12},  # other spelling
    ]})
    assert Researcher.objects.count() == before
    assert stays.metrics.get(metric="h_index").value == 12  # found by her OpenAlex id
