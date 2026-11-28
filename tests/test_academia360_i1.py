"""Academia360 sprint I.1: landing a researched institution

Avi, 2026-11-27: fill the empty institutions by public research, rich,
correct and interesting. The research is a JSON file per institution; the
loader lands it under the reference reading's rules:

- every fact lands with the source line and date of this pass;
- what is filled is never overwritten, and a second run adds nothing;
- values that do not fit (unknown kinds, non-http links, years out of range,
  Scholar links nobody can check) are dropped, never shaped into a guess;
- em dashes never reach the page;
- the coverage list then shows the institution as rich and researched.
"""
import json

import pytest
from django.core.management import call_command

from academia360 import coverage, research_load
from academia360.models import AgentRun, Criterion, Distinction, Institution, Program, Researcher

pytestmark = pytest.mark.django_db


def research():
    return {
        "slug": "gordon",
        "institution": {"name_en": "Gordon College", "founded": 1953, "tagline": "מכללה לחינוך בחיפה",
                        "identity": "מכללת גורדון — מכללה לחינוך בחיפה.", "website": "https://www.gordon.ac.il",
                        "identity_source_url": "https://www.gordon.ac.il/about"},
        "metrics": [{"key": "students_total", "value": "3,100", "year": 2025, "source": "אתר המכללה",
                     "source_url": "https://www.gordon.ac.il/facts"},
                    {"key": "Bad Key!", "value": 4}],
        "units": [{"name": "בית הספר לחינוך", "kind": "school", "students": 2000, "students_year": 2025,
                   "share_pct": 64.5, "source_url": "https://www.gordon.ac.il/facts"},
                  {"name": "בית הספר לתארים מתקדמים", "kind": "nonsense"}],
        "study_programs": [{"name": "הוראת מדעים", "degree": "B.Ed.", "level": "undergrad", "field": "education",
                            "unit": "בית הספר לחינוך"}],
        "sections": [{"kind": "overview", "title": "סקירה", "body": "גורדון היא מכללה ותיקה.",
                      "source_url": "https://www.gordon.ac.il/about"},
                     {"kind": "programs", "title": "תכניות", "body": "תכניות רבות."},
                     {"kind": "weird", "title": "חדשנות", "body": "מרכז לחדשנות בהוראה."}],
        "documents": [{"kind": "vision", "title": "החזון", "url": "https://www.gordon.ac.il/vision",
                       "summary": "מה המכללה רוצה.", "criteria": ["innovation", "nope"]},
                      {"kind": "vision", "title": "בלי קישור", "url": "javascript:alert(1)"}],
        "timeline": [{"year": 1953, "text": "המכללה נוסדה"}, {"year": 3020, "text": "שנה בלתי אפשרית"}],
        "centers": [{"name": "מרכז חדשנות", "focus": "הוראה", "url": "https://www.gordon.ac.il/c"}],
        "collaborations": [{"kind": "community", "partner": "עיריית חיפה", "description": "תכנית קהילה"},
                           {"kind": "space", "partner": "מאדים"}],
        "researchers": [{"name_he": "דנה לוי", "name_en": "Dana Levi", "title": "ד״ר", "position": "ראש החוג",
                         "unit": "בית הספר לחינוך", "focus": "הוראת מדעים", "kind": "applied",
                         "openalex_id": "https://openalex.org/A123", "h_index": 12, "citations": 480,
                         "links": [{"kind": "homepage", "url": "https://www.gordon.ac.il/dana"},
                                   {"kind": "scholar", "url": "https://scholar.google.com/citations?user=x"}],
                         "publications": [{"title": "Teaching science", "venue": "J. Ed.", "year": 2021,
                                           "citations": 40, "url": "https://doi.org/10.1/x"}],
                         "prizes": [{"kind": "other", "title": "פרס הוראה מצטיינת", "year": 2022}]},
                        {"name_he": "יוסי כהן", "title": "פרופ׳", "focus": "חינוך מיוחד"},
                        {"name_he": "רות שגיא", "title": "ד״ר", "focus": "מתמטיקה"}],
        "distinctions": [{"kind": "ranking", "title": "דירוג", "year": 2024, "url": "https://example.org/r",
                          "researcher_name_he": ""}],
        "gaps": "אין פיצול סטודנטים מלא",
        "sources": ["https://www.gordon.ac.il/about"],
    }


@pytest.fixture
def world(db):
    program = Program.objects.create(slug="academia-360", name="אקדמיה 360")
    Criterion.objects.create(program=program, slug="innovation", name="חדשנות בהוראה")
    return Institution.objects.create(slug="gordon", name_he="מכללת גורדון", kind=Institution.TEACHER, city="חיפה",
                                      founded=1950)


def test_a_research_file_lands_with_its_source_and_drops_what_does_not_fit(world):
    research_load.land(world, research())
    inst = Institution.objects.get(pk=world.pk)
    assert inst.founded == 1950  # filled already: never overwritten
    assert inst.name_en == "Gordon College" and inst.tagline
    assert "—" not in inst.identity and inst.identity_source.endswith("gordon.ac.il")
    assert list(inst.metrics.values_list("key", flat=True)) == ["students_total"]
    assert inst.metrics.get().value == 3100 and inst.metrics.get().source_url.endswith("/facts")
    school = inst.units.get(name="בית הספר לחינוך")
    assert school.kind == "school" and school.enrollments.get().students == 2000
    assert inst.units.get(name="בית הספר לתארים מתקדמים").kind == "faculty"
    assert inst.study_programs.get().unit == school
    assert inst.sections.count() == 3 and inst.sections.get(title="חדשנות").kind == "other"
    assert all(s.source.startswith(research_load.SOURCE) for s in inst.sections.all())
    doc = inst.public_documents.get()
    assert doc.url.endswith("/vision") and list(doc.criteria.values_list("slug", flat=True)) == ["innovation"]
    assert list(inst.timeline.values_list("year", flat=True)) == [1953]
    assert inst.centers.count() == 1 and inst.collaborations.count() == 1
    dana = inst.researchers.get(name_he="דנה לוי")
    assert dana.kind == "applied" and dana.unit == school and dana.position == "ראש החוג"
    assert {m.metric: m.value for m in dana.metrics.all()} == {"h_index": 12, "citations": 480}
    assert sorted(dana.links.values_list("url", flat=True)) == ["https://openalex.org/A123",
                                                                "https://www.gordon.ac.il/dana"]
    assert dana.publications.get().citations == 40
    assert dana.distinctions.get().title == "פרס הוראה מצטיינת"
    assert Distinction.objects.filter(institution=inst, researcher=None, kind="ranking").count() == 1
    assert inst.research_status == Institution.RESEARCH_IMPORTED and "אין פיצול" in inst.research_note


def test_a_second_run_adds_nothing_and_keeps_an_admin_edit(world):
    research_load.land(world, research())
    dana = Researcher.objects.get(name_he="דנה לוי")
    dana.focus = "נערך ביד"
    dana.save()
    counts = research_load.land(Institution.objects.get(pk=world.pk), research())
    assert sum(v[0] for v in counts.values()) == 0
    assert Researcher.objects.get(pk=dana.pk).focus == "נערך ביד"
    assert Researcher.objects.filter(institution=world).count() == 3


def test_the_coverage_list_reads_it_as_rich_and_the_command_records_a_run(world, tmp_path):
    assert coverage.rows()[0]["state"] == "empty"  # a founding year is not material
    f = tmp_path / "gordon.json"
    f.write_text(json.dumps(research(), ensure_ascii=False), encoding="utf-8")
    call_command("load_research", str(tmp_path), "--dry-run")
    assert world.sections.count() == 0 and not AgentRun.objects.exists()
    call_command("load_research", str(tmp_path))
    assert coverage.rows()[0]["state"] == "rich"
    assert AgentRun.objects.get().rows_touched > 20


def test_the_same_name_at_two_institutions_gets_two_addresses(world):
    other = Institution.objects.create(slug="carmel", name_he="כרמל", kind=Institution.COLLEGE, city="חיפה")
    research_load.land(world, research())
    data = research()
    data["slug"] = "carmel"
    research_load.land(other, data)
    a = Researcher.objects.get(institution=world, name_he="דנה לוי")
    b = Researcher.objects.get(institution=other, name_he="דנה לוי")
    assert a.slug != b.slug
    from django.test import Client
    assert Client().get(f"/academia360/researchers/{b.slug}/").status_code == 200


def test_markdown_in_a_section_and_a_bio_renders_and_never_shows_raw(world):
    from django.test import Client
    from academia360.models import ProfileSection
    ProfileSection.objects.create(institution=world, kind="structure", title="מבנה",
                                  body="- **הפקולטה לאמנויות**, בראשות הדיקן\n- **הפקולטה למחול**<script>x</script>")
    r = Researcher.objects.create(institution=world, slug="bio-md", name_he="רות", bio="**חוקרת** ותיקה")
    page = Client().get(f"/academia360/institutions/{world.slug}/").content.decode()
    assert "<strong>הפקולטה לאמנויות</strong>" in page and "**" not in page and "<script>x" not in page
    assert "<li>" in page
    bio = Client().get(f"/academia360/researchers/{r.slug}/").content.decode()
    assert "<strong>חוקרת</strong>" in bio and "**" not in bio


def test_the_map_tiles_ask_with_a_referrer():
    """OSM refuses tile requests without a Referer, and the site's default
    policy sends none cross-origin (the map showed 'Access blocked')."""
    from pathlib import Path
    js = (Path(__file__).resolve().parent.parent / "static" / "academia360" / "a360.js").read_text(encoding="utf-8")
    assert 'referrerPolicy: "strict-origin-when-cross-origin"' in js
