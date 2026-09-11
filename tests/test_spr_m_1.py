"""SPR-M.1 — The front door.

The מט״צים space becomes its own product: its own Django app, its own base
template, its own design, its own menu, and no route back to babook in either
direction. This sprint is design-first, so the home page is Litala's screen 1
with every value hardcoded. There is no data layer here yet.

Traces: REQ-M.1, REQ-M.3, REQ-M.5, REQ-M.5b, REQ-M.5c, REQ-M.5d, REQ-M.5f,
and the four separation rules in docs/matazim/spec.md section 2.3.
"""

import re
from pathlib import Path

import pytest
from django.conf import settings
from django.urls import reverse

pytestmark = pytest.mark.sprm1

ROOT = Path(settings.BASE_DIR)
MZ_TEMPLATES = ROOT / "templates" / "matazim"
MZ_APP = ROOT / "matazim"


def _templates():
    return sorted(MZ_TEMPLATES.rglob("*.html")) if MZ_TEMPLATES.exists() else []


def _py(pkg: Path):
    return sorted(pkg.rglob("*.py")) if pkg.exists() else []


# ---------------------------------------------------------------- F-M.1.1


def test_babook_home_has_no_matazim_link(client, db):
    """T-F-M.1.1-1: babook must not advertise מט״צים anywhere in its chrome."""
    html = client.get("/").content.decode()
    assert "/matazim" not in html


def test_show_matazim_context_processor_is_gone():
    """T-F-M.1.1-2: the per-request membership query on every page load is removed."""
    from app import context_processors

    src = Path(context_processors.__file__).read_text(encoding="utf-8")
    assert "show_matazim" not in src


def test_old_presentation_files_are_deleted():
    """T-F-M.1.1-3: the embedded version's front end no longer exists."""
    for gone in (
        ROOT / "app" / "matazim_views.py",
        ROOT / "templates" / "app" / "matazim",
        ROOT / "static" / "matazim.css",
        ROOT / "tests" / "test_spr_10_1.py",
    ):
        assert not gone.exists(), f"{gone} should have been removed by the sever"


def test_data_layer_and_entrance_engine_survive():
    """T-F-M.1.1-4: the sever removes presentation only. Nothing is destroyed."""
    from app import matazim_check, matazim_geometry, matazim_models, matazim_targets

    assert matazim_models.Program is not None
    assert all(m is not None for m in (matazim_geometry, matazim_check, matazim_targets))
    assert (ROOT / "app" / "management" / "commands" / "seed_matazim.py").exists()


def test_babook_still_serves(client, db):
    """T-F-M.1.1-5: RULE-4 in practice. Removing the hooks broke nothing."""
    assert client.get("/").status_code == 200


# ---------------------------------------------------------------- F-M.1.2


def test_matazim_is_an_installed_app():
    """T-F-M.1.2-1."""
    assert "matazim" in settings.INSTALLED_APPS


def test_home_responds(client, db):
    """T-F-M.1.2-2."""
    assert client.get("/matazim/").status_code == 200


def test_home_reverses_under_its_own_namespace():
    """T-F-M.1.2-3: מט״צים owns its URL names, so they can never collide."""
    assert reverse("matazim:home") == "/matazim/"


# ---------------------------------------------------------------- F-M.1.3


def test_stylesheet_defines_the_design_tokens():
    """T-F-M.1.3-1: teal is identity, purple is action, per spec 3.2."""
    css = (ROOT / "static" / "matazim" / "matazim.css").read_text(encoding="utf-8")
    for token in (
        "--mz-teal",
        "--mz-purple",
        "--mz-blue",
        "--mz-ink",
        "--mz-page",
        "--mz-card",
    ):
        assert token in css, f"missing design token {token}"


def test_page_uses_rubik_and_never_babook_css(client, db):
    """T-F-M.1.3-2: a different typeface is half of reading as a different product.

    Rubik used to be findable in the markup, because the page carried a Google
    Fonts <link>. SPR-M.9 removed it: that link sent every visitor's IP to
    Google on every page load, on a site whose visitors are fourteen. The
    typeface is still Rubik, so this now asks the stylesheet, which is where
    the answer moved to.
    """
    from pathlib import Path

    html = client.get("/matazim/").content.decode()
    assert "matazim/matazim.css" in html
    assert not re.search(r"static/style\.css|/static/style\.css", html)

    css = Path("static/matazim/matazim.css").read_text(encoding="utf-8")
    assert "Rubik" in css
    assert "fonts.googleapis.com" not in html and "fonts.gstatic.com" not in html


# ---------------------------------------------------------------- F-M.1.4


def test_page_carries_none_of_babook_chrome(client, db):
    """T-F-M.1.4-1: RULE-2, checked through the rendered page rather than the source."""
    html = client.get("/matazim/").content.decode()
    for marker in ("babook", "site-drawer", "nav-link px-2", "bi-cpu"):
        assert marker not in html, f"babook chrome leaked into מט״צים: {marker}"


def test_logged_out_nav_matches_the_prototype(client, db):
    """T-F-M.1.4-2: Litala's screen 1 menu, and it belongs to this app alone."""
    html = client.get("/matazim/").content.decode()
    items = [
        "דף הבית",
        "אודות התכנית",
        "המסלול השנתי",
        "הקורסים",
        "מבחן הכניסה",
        "בתי הספר",
        "קהילת מט״צים",
        "ימי שיא",
    ]
    positions = [html.find(item) for item in items]
    assert all(p != -1 for p in positions), "a nav item is missing"
    assert positions == sorted(positions), "nav items are out of the prototype's order"


def test_document_is_hebrew_and_rtl(client, db):
    """T-F-M.1.4-3."""
    html = client.get("/matazim/").content.decode()
    assert 'lang="he"' in html
    assert 'dir="rtl"' in html


def test_shell_chrome_renders(client, db):
    """T-F-M.1.4-4: the wordmark and the sign-in action live in the header."""
    html = client.get("/matazim/").content.decode()
    assert "matazim/logo.png" in html
    assert "התחברות" in html


# ---------------------------------------------------------------- F-M.1.5


def test_hero_renders(client, db):
    """T-F-M.1.5-1.

    The copy is Avi's, settled 2026-09-09: an educational program run with
    Intel volunteers, middle school rather than ninth grade, and the מט״צ goes
    on to teach in the high school once certified. The partner organisations
    moved out of the hero and into the footer, checked separately.
    """
    html = client.get("/matazim/").content.decode()
    hero = html.split('class="mz-hero-text"')[1].split("</p>")[0]
    assert "מט״צים" in html
    assert "מנהיגות טכנולוגית צעירה" in html
    assert "מתנדבי אינטל" in hero
    assert "חטיבת הביניים" in hero
    assert "בתיכון" in hero


def test_two_front_doors_and_the_public_test(client, db):
    """T-F-M.1.5-2: REQ-M.5c and REQ-M.5d, both drawn on screen 1."""
    html = client.get("/matazim/").content.decode()
    assert "כניסת תלמידים" in html
    assert "כניסת מובילים" in html
    assert "מבחן הכניסה" in html


def test_how_it_works_shows_four_stages_in_order(client, db):
    """T-F-M.1.5-3: the public path is four stages; מתמיינים is the entrance test."""
    html = client.get("/matazim/").content.decode()
    start = html.find("איך זה עובד")
    assert start != -1
    section = html[start:]
    positions = [section.find(s) for s in ("לומדים", "יוצרים", "מדריכים", "משפיעים")]
    assert all(p != -1 for p in positions)
    assert positions == sorted(positions)


def test_page_carries_no_invented_figures(client, db):
    """T-F-M.1.5-4: the counters stay off the page until something computes them.

    The prototype shows 1,250 students and 28 schools. Nobody counted those, so
    publishing them would be a claim we cannot stand behind. REQ-M.5f brings the
    band back when it reads from real rows.
    """
    html = client.get("/matazim/").content.decode()
    assert "mz-stats" not in html
    for invented in ("1,250", "4,300", "תוצרים שהוגשו", "בתי ספר"):
        assert invented not in html


def test_page_shows_no_invented_student_work(client, db):
    """T-F-M.1.5-5: no showcase until real projects exist and consent is real.

    REQ-M.5e makes publishing a member's work opt-in plus a staff decision, and
    REQ-M.11 (Q11) has not settled who consents for a minor. Until then the
    public page shows no children's projects at all, invented ones included.
    """
    html = client.get("/matazim/").content.decode()
    assert "mz-project-card" not in html
    assert "תוצרים נבחרים" not in html


def test_photographs_degrade_to_a_gradient(client, db):
    """T-F-M.1.5-6: a photo that has not been supplied must not show a broken image."""
    html = client.get("/matazim/").content.decode()
    assert "<img" not in html.split("mz-hero-media")[1].split("</section>")[0]
    assert "mz-photo" in html


def test_partners_section_carries_weight(client, db):
    """T-F-M.1.5-7: REQ-M.5g.

    Avi's instruction: the partners are not small print. They get a section of
    their own, high on the page, with their own marks. Position is part of the
    requirement, so the test checks the order rather than only the presence.
    """
    html = client.get("/matazim/").content.decode()
    assert "שותפים מרכזיים לעשייה" in html
    assert "partners/atid.svg" in html
    assert "partners/hemed_logo.png" in html
    assert "וגופים נוספים נפלאים" in html
    assert html.index("שותפים מרכזיים לעשייה") < html.index("איך זה עובד")


# ---------------------------------------------------------------- F-M.1.6


def test_rule_1_no_outbound_links():
    """T-F-M.1.6-1: no מט״צים template may link anywhere outside its own prefix."""
    offenders = []
    for tpl in _templates():
        src = tpl.read_text(encoding="utf-8")
        for name in re.findall(r"{%\s*url\s+['\"]([^'\"]+)['\"]", src):
            if not name.startswith("matazim:"):
                offenders.append(f"{tpl.name}: {{% url '{name}' %}}")
        for href in re.findall(r'href="(/[^"]*)"', src):
            if not href.startswith("/matazim/"):
                offenders.append(f"{tpl.name}: href={href}")
    assert not offenders, "RULE-1 broken: " + "; ".join(offenders)


def test_rule_2_no_shared_chrome():
    """T-F-M.1.6-2: no מט״צים template stands on a babook template."""
    assert _templates(), "no מט״צים templates found"
    for tpl in _templates():
        src = tpl.read_text(encoding="utf-8")
        for tag in re.findall(r"{%\s*(?:extends|include)\s+['\"]([^'\"]+)['\"]", src):
            assert tag.startswith("matazim/"), f"{tpl.name} reaches into {tag}"


def test_rule_3_keeps_one_version_of_the_truth():
    """T-F-M.1.6-3: no parallel record of what anyone has learned.

    Amended 2026-09-10. This first forbade every write, and threw at the first
    lesson we rendered: you cannot watch a lesson without an enrolment, and
    babook's own lesson view creates one with this exact one-liner in six
    places. The danger was never enrolment, it was divergence. So what is banned
    is fabricating progress, issuing a certificate by hand, and keeping a second
    table of our own.
    """
    forbidden = re.compile(
        r"(UserVideoProgress|CourseCertificate|TeacherClass|ClassMembership)"
        r"\.objects\.(create|update|get_or_create|update_or_create|bulk_create)"
    )

    # One exemption, named rather than pattern-matched so it cannot widen by
    # accident. `seed_matazim_demo` fabricates a world of imaginary people to
    # judge the screens against, and fabricating progress is its entire job:
    # there is no learner and no video, so there is no real code path to route
    # through. The rule exists to stop *product* code inventing a second way to
    # record learning, and this never runs for a real user. Its accounts are all
    # on demo.invalid, which cannot resolve.
    #
    # Amended 2026-09-11, when the guard caught the seeder on the day it was
    # written. The guard was right to; the answer is a narrow exemption with a
    # reason attached, not a looser pattern.
    exempt = {"seed_matazim_demo.py"}

    for src_file in _py(MZ_APP):
        if src_file.name in exempt:
            continue
        assert not forbidden.search(
            src_file.read_text(encoding="utf-8")
        ), f"RULE-3 broken in {src_file.name}: learning state written directly"

    # And no model of our own that shadows learning state.
    models_src = (MZ_APP / "models.py").read_text(encoding="utf-8")
    for shadow in ("class Enrollment", "class Progress", "class Certificate"):
        assert shadow not in models_src, f"RULE-3 broken: {shadow} duplicates babook"


def test_rule_4_babook_never_imports_matazim():
    """T-F-M.1.6-4: the dependency arrow points one way only."""
    bad = re.compile(r"^\s*(from\s+matazim|import\s+matazim)", re.M)
    offenders = [
        f.relative_to(ROOT).as_posix()
        for f in _py(ROOT / "app")
        if bad.search(f.read_text(encoding="utf-8"))
    ]
    assert not offenders, "RULE-4 broken: " + ", ".join(offenders)
