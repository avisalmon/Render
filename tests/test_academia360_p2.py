"""Academia360 sprint P.2: the second reading of the reference, by meaning

- two small pages in two vocabularies (a card with value-then-label metrics
  and an <h3> name; a card with label-then-value boxes and an English name)
  land the same kind of rows: position, unit, focus, bio, dated metrics,
  publications, links, prizes;
- the overview page lands a tagline, facts, a faculty split, a timeline and
  sections with kinds;
- a second run changes nothing; a filled field is never overwritten; an
  area heading the first import took for a person is turned off;
- the real reference folder, when it is on this PC, yields at least what we
  measured on 2026-11-27 (and the music academy stays empty).
"""
from pathlib import Path

import pytest

from academia360 import reference_pages as pages
from academia360 import reread
from academia360.management.commands.import_reference import DEFAULT_ROOT
from academia360.models import (
    Distinction,
    Institution,
    InstitutionMetric,
    ProfileSection,
    Publication,
    Researcher,
    ResearcherMetric,
    TimelineEvent,
    Unit,
    UnitEnrollment,
)

pytestmark = pytest.mark.django_db

PAGE_A = """<html><body>
<h1>חוקרים מובילים</h1>
<div class="researcher-card">
  <div class="researcher-header"><div class="researcher-info">
    <h3><span class="nobel-badge">נובל 2004</span> פרופ' אהרן צ'חנובר</h3>
    <div class="title">פקולטה לרפואה | ביוכימיה</div>
    <div class="focus">מנגנון יוביקוויטין לפירוק חלבונים</div>
  </div></div>
  <p>זוכה פרס נובל לכימיה (2004) יחד עם פרופ' הרשקו על גילוי מנגנון היוביקוויטין, מערכת תאית המסמנת חלבונים לפירוק.</p>
  <div class="publications"><h4>פרסומים מייצגים</h4>
    <div class="publication-item"><div class="title">"A Polypeptide for Specific Attachment of Ubiquitin"</div><div class="venue">Nature, 1980</div></div>
  </div>
  <div class="links"><a href="https://www.technion.ac.il/en/people/ciechanover/" class="link-btn">דף אישי</a></div>
</div>
<div class="researcher-card">
  <div class="researcher-header"><div class="researcher-info">
    <h3>פרופ' שי מנור (Shie Mannor)</h3>
    <div class="title">פקולטה להנדסת חשמל ומחשבים | מופקד קתדרה</div>
    <div class="focus">למידת חיזוק ובקרה תחת אי-ודאות</div>
  </div></div>
  <div class="metrics">
    <div class="metric"><span class="value">~90</span><span class="label">h-index</span></div>
    <div class="metric"><span class="value">33,000+</span><span class="label">ציטוטים</span></div>
    <div class="metric"><span class="value">2025</span><span class="label">נכון ל</span></div>
  </div>
  <p><strong>תחומי מחקר:</strong> חלוץ באלגוריתמי למידת חיזוק לפתרון בעיות תפעול מורכבות, עם יישומים ברשתות חשמל ובתחבורה.</p>
  <div class="links"><a href="https://scholar.google.com/citations?user=abcd1234" class="link-btn">Google Scholar</a>
    <a href="https://dblp.org/pid/12/345" class="link-btn">DBLP</a></div>
</div>
<h3>הערה חשובה</h3><p>המדדים נלקחו מפרופילים ציבוריים.</p>
</body></html>"""

PAGE_B = """<html><body>
<h1>🧑‍🔬 חוקרים מובילים</h1>
<h2>🤖 חוקרי בינה מלאכותית מובילים</h2>
<div class="researcher-card">
  <div class="researcher-name">Dr. Zohar Barnett-Itzhaki</div>
  <div class="researcher-title">Senior Lecturer | הנדסה וקיימות</div>
  <div class="researcher-focus"><strong>🎯 התמחות:</strong> Environmental Data Science &amp; AI for Public Health</div>
  <div class="metrics">
    <div class="metric-box"><div class="metric-label">h-index</div><div class="metric-value">21</div></div>
    <div class="metric-box"><div class="metric-label">ציטוטים</div><div class="metric-value">1,200+</div></div>
  </div>
  <div class="publications"><h4>📄 פרסומים בולטים (2023-2025)</h4><ul>
    <li><strong>Amitay et al., 2023, PLOS Digital Health</strong> - זיהוי הסתיידויות בעורקים מצילומי שיניים</li>
    <li><strong>Barnett-Itzhaki et al., 2023, Atmosphere</strong> - מודל לחיזוי התפשטות COVID-19</li>
  </ul></div>
  <div><strong>💰 מענקים:</strong> <span class="badge">Horizon 2020 (HBM4EU)</span></div>
</div>
<div class="researcher-card">
  <div class="researcher-name">פרופ' Israel Katz (ישראל כ"ץ)</div>
  <div class="researcher-title">Emeritus | בית הספר להנדסה</div>
  <span class="highlight-badge">פרס ישראל להנדסה 2019</span>
  <span class="highlight-badge">ORCID: 0000-0002-2113-4780</span>
</div>
</body></html>"""

OVERVIEW = """<html><body>
<div class="institution-hero"><h1>הטכניון - מכון טכנולוגי לישראל</h1>
<div class="hero-stats">
  <div class="hero-stat"><span class="number">1912</span><span class="label">שנת ייסוד</span></div>
  <div class="hero-stat"><span class="number">15,000+</span><span class="label">סטודנטים</span></div>
  <div class="hero-stat"><span class="number">600+</span><span class="label">חברי סגל</span></div>
  <div class="hero-stat"><span class="number">18</span><span class="label">פקולטות</span></div>
</div></div>
<h2>סקירה כללית</h2>
<p>מוסד אקדמי מוביל עולמי במדע, הנדסה וטכנולוגיה</p>
<div class="info-card"><h3>ייסוד ומעמד</h3><p>הטכניון נוסד בשנת 1912 והחל בהוראה ב-1924. זהו המוסד הראשון להשכלה גבוהה בארץ ישראל, המתמקד בהנדסה ובמדעים מדויקים.</p></div>
<h2>התפלגות סטודנטים לפי פקולטות</h2>
<div class="faculty-grid">
  <div class="faculty-item"><div class="percentage">18%</div><div class="name">הנדסת חשמל ומחשבים</div><div class="students">~1,900 סטודנטים</div></div>
  <div class="faculty-item"><div class="percentage">15%</div><div class="name">מדעי המחשב (טאוב)</div><div class="students">~1,600 סטודנטים</div></div>
</div>
<h2>מצוינות מחקרית</h2>
<ul><li>מכוני מחקר מובילים ותחומי התמחות ברמה עולמית</li><li>ננו-טכנולוגיה, אנרגיה, בינה מלאכותית ורפואה מדויקת כתחומי דגל</li></ul>
<h2>ציוני דרך היסטוריים</h2>
<div class="timeline">
  <div class="timeline-item"><div class="year">1912</div><div class="event">הנחת אבן הפינה לטכניון וניצחון העברית כשפת ההוראה</div></div>
  <div class="timeline-item"><div class="year">2004</div><div class="event">פרס נובל לכימיה לפרופ' צ'חנובר והרשקו</div></div>
</div>
<h2>רוצים לגלות עוד?</h2><p>קישורים שימושיים לאתר הטכניון ולמרכזי המחקר שלו, ועוד.</p>
</body></html>"""


@pytest.fixture
def inst(db):
    return Institution.objects.create(slug="technion", name_he="הטכניון", kind=Institution.UNIVERSITY, city="חיפה")


def test_a_card_with_value_then_label_metrics_reads_whole(inst):
    people = pages.read_people(PAGE_A)
    assert [p["name_he"] for p in people] == ["אהרן צ'חנובר", "שי מנור"], "the note heading is not a person"
    aaron, shie = people
    assert aaron["title"] == "פרופ׳" and aaron["unit"] == "פקולטה לרפואה" and aaron["focus"].startswith("מנגנון")
    assert aaron["prizes"] == [("nobel", "פרס נובל לכימיה", 2004)]
    assert aaron["publications"][0][:2] == ("A Polypeptide for Specific Attachment of Ubiquitin", "Nature, 1980")
    assert aaron["publications"][0][2] == 1980 and aaron["links"] == [("homepage", "https://www.technion.ac.il/en/people/ciechanover/")]
    assert "זוכה פרס נובל" in aaron["bio"]
    assert shie["name_en"] == "Shie Mannor" and shie["unit"] == "פקולטה להנדסת חשמל ומחשבים"
    assert (shie["h_index"], shie["h_approx"], shie["citations"], shie["cites_approx"], shie["as_of_year"]) == (90, True, 33000, True, 2025)
    assert {k for k, _ in shie["links"]} == {"scholar", "dblp"} and shie["bio"].startswith("חלוץ")


def test_a_card_with_label_then_value_boxes_and_an_english_name_reads_the_same_fields():
    zohar, katz = pages.read_people(PAGE_B)
    assert zohar["name_en"] == "Zohar Barnett-Itzhaki" and zohar["name_he"] == "" and zohar["title"] == "ד״ר"
    assert zohar["position"] == "Senior Lecturer" and zohar["focus"].startswith("Environmental Data Science & AI")
    assert (zohar["h_index"], zohar["citations"], zohar["cites_approx"]) == (21, 1200, True), "the label's own box is not its value"
    assert len(zohar["publications"]) == 2 and zohar["publications"][0][2] == 2023
    assert zohar["publications"][0][0].startswith("Amitay et al., 2023"), "a citation-style line stays whole"
    assert katz["name_he"] == "ישראל כ\"ץ" and katz["name_en"] == "Israel Katz" and katz["unit"] == "בית הספר להנדסה"
    assert katz["prizes"] == [("israel_prize", "פרס ישראל להנדסה 2019", 2019)]
    assert ("orcid", "https://orcid.org/0000-0002-2113-4780") in katz["links"]


def test_the_overview_page_reads_tagline_facts_split_timeline_and_sections():
    o = pages.read_overview(OVERVIEW)
    assert o["tagline"] == "מוסד אקדמי מוביל עולמי במדע, הנדסה וטכנולוגיה"
    facts = {k: (v, approx) for k, v, approx, year, label in o["facts"]}
    assert facts["founded"] == (1912, False) and facts["students_total"] == (15000, True)
    assert facts["faculty_total"] == (600, True) and facts["faculties_count"] == (18, False)
    assert o["split"] == [("הנדסת חשמל ומחשבים", 1900, True, 18.0), ("מדעי המחשב (טאוב)", 1600, True, 15.0)]
    assert [y for y, _ in o["timeline"]] == [1912, 2004]
    titles = [(t, k) for t, k, _ in o["sections"]]
    assert ("סקירה כללית", "overview") in titles and ("מצוינות מחקרית", "research") in titles
    assert not any("רוצים" in t or "ציוני דרך" in t or "התפלגות" in t for t, _ in titles)


def test_landing_fills_only_what_is_empty_and_a_second_run_changes_nothing(inst):
    old = Researcher.objects.create(institution=inst, slug="mannor", name_he="שי מנור (Shie Mannor)", title="פרופ'",
                                    areas="למידת חיזוק", focus="הטקסט של אבי, שנשאר")
    Researcher.objects.create(institution=inst, slug="note", name_he="הערה חשובה")  # the first import's slip
    counts = reread.reread(inst, _folder(PAGE_A, OVERVIEW))[0]
    old.refresh_from_db()
    assert old.name_he == "שי מנור" and old.name_en == "Shie Mannor", "the English half moves to its own field"
    assert old.focus == "הטקסט של אבי, שנשאר", "a filled field is never overwritten"
    assert old.unit.name == "פקולטה להנדסת חשמל ומחשבים" and old.position == "מופקד קתדרה" and old.bio.startswith("חלוץ")
    h = ResearcherMetric.objects.get(researcher=old, metric="h_index")
    assert (h.value, h.approximate, str(h.as_of)) == (90, True, "2025-01-01")
    aaron = Researcher.objects.get(institution=inst, name_he="אהרן צ'חנובר")
    assert aaron.is_leading and Publication.objects.filter(researcher=aaron).count() == 1
    assert Distinction.objects.get(researcher=aaron).year == 2004
    assert not Researcher.objects.get(slug="note").verified, "an area heading is not a person"
    inst.refresh_from_db()
    assert inst.tagline.startswith("מוסד אקדמי") and inst.founded == 1912 and inst.research_status == "imported"
    assert InstitutionMetric.objects.filter(institution=inst, key="students_total", value=15000).exists()
    assert UnitEnrollment.objects.filter(unit__institution=inst).count() == 2
    assert Unit.objects.filter(institution=inst, name="מדעי המחשב (טאוב)").exists()
    assert TimelineEvent.objects.filter(institution=inst).count() == 2
    assert ProfileSection.objects.filter(institution=inst, kind="research").exists()
    before = _snapshot(inst)
    again = reread.reread(inst, _folder(PAGE_A, OVERVIEW))[0]
    assert _snapshot(inst) == before and sum(v[0] for v in again.values()) == 0, dict(again)
    assert counts["researchers"][0] == 1  # one new person (Aaron); Shie was matched


def test_an_institution_without_pages_is_left_exactly_as_it_is(inst, tmp_path):
    counts, read = reread.reread(inst, tmp_path)
    inst.refresh_from_db()
    assert read == [] and not counts and inst.research_status == "none" and inst.identity == ""


@pytest.mark.skipif(not (DEFAULT_ROOT / "data" / "institutions.json").exists(), reason="the reference lives on Avi's PC")
def test_the_real_reference_yields_at_least_what_we_measured():
    root = DEFAULT_ROOT / "documents" / "proposals"
    people = pubs = h = timeline = split = 0
    for folder in root.iterdir():
        for name in ("researchers.html", "leading_researchers.html"):
            if (folder / name).exists():
                ps = pages.read_people((folder / name).read_text(encoding="utf-8", errors="replace"))
                people += len(ps)
                pubs += sum(len(p["publications"]) for p in ps)
                h += sum(1 for p in ps if p["h_index"])
                assert not any(p["h_index"] and p["h_index"] == p["citations"] for p in ps), folder.name
        if (folder / "index.html").exists():
            o = pages.read_overview((folder / "index.html").read_text(encoding="utf-8", errors="replace"))
            timeline += len(o["timeline"])
            split += len(o["split"])
    assert people >= 255 and pubs >= 300 and h >= 75 and timeline >= 100 and split >= 40, (people, pubs, h, timeline, split)
    assert not (root / "האקדמיה למוסיקה" / "index.html").exists(), "the music academy has no material; it stays empty"


def _folder(people_html, overview_html, base=None):
    import tempfile
    d = Path(base or tempfile.mkdtemp())
    (d / "researchers.html").write_text(people_html, encoding="utf-8")
    (d / "index.html").write_text(overview_html, encoding="utf-8")
    return d


def _snapshot(inst):
    return (
        list(Researcher.objects.filter(institution=inst).values_list("slug", "name_he", "name_en", "position", "focus", "bio", "verified")),
        list(ResearcherMetric.objects.filter(researcher__institution=inst).values_list("metric", "value", "as_of")),
        list(Publication.objects.filter(researcher__institution=inst).values_list("title", "venue", "year")),
        list(Distinction.objects.filter(institution=inst).values_list("kind", "title", "year")),
        list(TimelineEvent.objects.filter(institution=inst).values_list("year", "text")),
        list(ProfileSection.objects.filter(institution=inst).values_list("title", "kind", "order")),
        list(UnitEnrollment.objects.filter(unit__institution=inst).values_list("unit__name", "students", "share_pct")),
        list(InstitutionMetric.objects.filter(institution=inst).values_list("key", "value", "year")),
        (inst.tagline, inst.founded, inst.identity),
    )
