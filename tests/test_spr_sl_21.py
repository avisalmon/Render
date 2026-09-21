"""SL-M1 — SensorLab: mathematics, and an explanation that earns it.

See docs/sensorlab/backlog.md (SL-M1).

Avi opened the Learn step on his own phone and said the explanation was too
thin and the formulas should be LaTeX. He was right on both counts: the
screen showed `|a| = √(a_x² + a_y² + a_z²)` as plain text in a grey box, and
three short paragraphs where the lab should be teaching *why* an
accelerometer measures gravity at all.

**The bug hiding underneath that request.** Markdown eats mathematics.
`$a_x^2$` through a Markdown renderer becomes `$a<em>x^2$` — the underscore
is read as emphasis and the formula is silently corrupted. It looks like a
typo in the course, not like a rendering fault, which is the worst kind of
wrong. So math spans are lifted out before conversion and put back after,
and the test for that matters more than the one for KaTeX loading.

**Escaped, but not Markdowned.** SL-B1 decided no HTML is ever produced from
author input. Math is still escaped for HTML — KaTeX reads `textContent`, so
an escaped `&lt;` arrives at the renderer as `<` and the inequality works —
it simply does not go through Markdown.
"""

import pytest

pytestmark = [pytest.mark.sprsl21, pytest.mark.django_db]

PASSWORD = "sensorlab-test-passw0rd"
LAB = "measuring-g"


def _seed():
    from io import StringIO

    from django.core.management import call_command

    call_command("seed_sensorlab", stdout=StringIO())


def _block(**kw):
    from sensorlab.models import ContentBlock

    return ContentBlock(**kw)


# ------------------------------------------------- math survives Markdown


def test_markdown_does_not_eat_mathematics():
    """The bug, as it actually is rather than as I first assumed.

    I claimed from memory that `$a_x^2$` becomes `$a<em>x^2$`. It does not:
    python-markdown will not emphasise inside a word, so intra-word
    subscripts were never at risk — measured before being "fixed".

    What IS corrupted is any `*` inside maths and any `_` with spaces
    around it, both of which are ordinary LaTeX:

        $a*b*c$     ->  $a<em>b</em>c$
        $x _y_ z$   ->  $x <em>y</em> z$

    Silently, and looking like an author's typo rather than a rendering
    fault, which is the worst way for a course to be wrong.
    """
    from sensorlab.models import ContentBlock

    for body in ("A product: $a*b*c$ appears.",
                 "Spaced: $x _y_ z$ appears.",
                 "Intra-word: $a_x^2 + a_y^2$ appears."):
        out = _block(kind=ContentBlock.Kind.TEXT, body_en=body).render("en")
        assert "<em>" not in out, f"Markdown got inside the maths: {body!r} -> {out}"

    kept = _block(kind=ContentBlock.Kind.TEXT,
                  body_en="The magnitude is $a_x^2 + a_y^2 + a_z^2$ under a root.").render("en")
    assert "a_x^2 + a_y^2 + a_z^2" in kept


def test_display_math_survives_intact():
    from sensorlab.models import ContentBlock

    block = _block(kind=ContentBlock.Kind.TEXT,
                   body_en="Therefore:\n\n$$\\vec{a}_{\\text{proper}} = \\vec{a} - \\vec{g}$$\n\nwhich is the whole story.")
    out = block.render("en")

    assert "\\vec{a}_{\\text{proper}}" in out, "the backslashes did not survive"
    assert "$$" in out, "the delimiters KaTeX looks for are gone"
    assert "<em>" not in out


def test_markdown_still_works_around_the_maths():
    """Protecting math must not turn the rest of the page into plain text."""
    from sensorlab.models import ContentBlock

    block = _block(kind=ContentBlock.Kind.TEXT,
                   body_en="This is **important**: $g \\approx 9.81$ is *not* a law.")
    out = block.render("en")

    assert "<strong>important</strong>" in out
    assert "<em>not</em>" in out
    assert "9.81" in out


def test_maths_is_still_escaped_for_html():
    """SL-B1's rule holds inside formulas too: no HTML from author input.

    KaTeX reads `textContent`, so an escaped `&lt;` reaches the renderer as
    `<` and an inequality typesets correctly — escaping costs nothing and
    keeps the guarantee whole.
    """
    from sensorlab.models import ContentBlock

    block = _block(kind=ContentBlock.Kind.TEXT,
                   body_en="Free fall gives $a < 0.1$ and <script>alert(1)</script>.")
    out = block.render("en")

    assert "<script>" not in out
    assert "&lt;script&gt;" in out
    assert "&lt; 0.1" in out or "&lt;0.1" in out


def test_a_formula_block_is_still_literal():
    """Formula blocks never went through Markdown (SL-B3), and still do not.
    They are now simply expected to contain LaTeX."""
    from sensorlab.models import ContentBlock

    block = _block(kind=ContentBlock.Kind.FORMULA,
                   body_en="$$|\\vec{a}| = \\sqrt{a_x^2 + a_y^2 + a_z^2}$$")
    out = block.render("en")

    assert "\\sqrt{a_x^2 + a_y^2 + a_z^2}" in out
    assert "<p>" not in out


def test_text_with_a_lone_dollar_is_not_treated_as_maths():
    """A price is not a formula. An unpaired `$` must not swallow the rest
    of the paragraph looking for a partner."""
    from sensorlab.models import ContentBlock

    block = _block(kind=ContentBlock.Kind.TEXT,
                   body_en="The sensor costs about $2 to make, which is the point.")
    out = block.render("en")

    assert "$2 to make" in out
    assert "<p>" in out


# ------------------------------------------------------------- it renders


def test_katex_is_loaded_on_the_lab_pages(client, django_user_model):
    """Vendored locally at `static/katex/`, already used by another page on
    this site. Not a new dependency, and not a Rule 2 breach — a
    third-party library in shared `static/` is the same category as Rubik.
    """
    from sensorlab.models import Lab, LabAttempt

    _seed()
    user = django_user_model.objects.create_user("ada", password=PASSWORD)
    LabAttempt.objects.start(user=user, lab=Lab.objects.get(slug=LAB))
    client.force_login(user)

    html = client.get(f"/sensorlab/lab/{LAB}/run/intro/", follow=True).content.decode()
    assert "katex.min.css" in html
    assert "katex.min.js" in html
    assert "renderMathInElement" in html


def test_the_renderer_is_told_about_both_delimiters(client, django_user_model):
    """Display maths and inline maths both appear in this course, and
    auto-render only handles what it is given."""
    from sensorlab.models import Lab, LabAttempt

    _seed()
    user = django_user_model.objects.create_user("ada", password=PASSWORD)
    LabAttempt.objects.start(user=user, lab=Lab.objects.get(slug=LAB))
    client.force_login(user)

    html = client.get(f"/sensorlab/lab/{LAB}/run/intro/", follow=True).content.decode()
    assert "display: true" in html
    assert "display: false" in html


# -------------------------------------------------- the explanation itself


def test_the_learn_step_actually_derives_the_result():
    """Not "an accelerometer measures proper acceleration" and a full stop.

    The question a student is owed an answer to is *why gravity is measured
    as an acceleration at all* — which needs the proof mass, Newton's second
    law, and the two cases that fall out of it.
    """
    from sensorlab.models import ContentBlock, Lab

    _seed()
    lab = Lab.objects.get(slug=LAB)
    learn = " ".join(
        b.body_en for b in lab.content_blocks.filter(step=ContentBlock.Step.LEARN)
    )

    for idea in ("proof mass", "Newton", "free fall", "equivalence"):
        assert idea.lower() in learn.lower(), f"the Learn step never mentions {idea}"

    # The two cases that make the whole thing click.
    assert "\\vec{a}" in learn, "no vector notation anywhere"
    assert learn.count("$$") >= 4, "fewer than two display formulas"


def test_the_derivation_exists_in_both_languages():
    from sensorlab.models import ContentBlock, Lab

    _seed()
    lab = Lab.objects.get(slug=LAB)
    for block in lab.content_blocks.filter(step=ContentBlock.Step.LEARN):
        assert block.body_he.strip(), f"block {block.pk} has no Hebrew"
        if block.kind != ContentBlock.Kind.FORMULA:
            assert block.body_en != block.body_he, f"block {block.pk} is untranslated"


def test_the_maths_is_identical_in_both_languages():
    """Prose is translated; equations are not. A formula that differs
    between languages is a transcription error, not a translation."""
    import re

    from sensorlab.models import ContentBlock, Lab

    _seed()
    lab = Lab.objects.get(slug=LAB)
    display = re.compile(r"\$\$(.+?)\$\$", re.S)

    for block in lab.content_blocks.filter(step=ContentBlock.Step.LEARN):
        english = [m.strip() for m in display.findall(block.body_en)]
        hebrew = [m.strip() for m in display.findall(block.body_he)]
        assert english == hebrew, (
            f"block {block.pk}: the display formulas differ between languages\n"
            f"  en: {english}\n  he: {hebrew}"
        )


def test_the_old_plain_text_formula_is_gone():
    """The thing on Avi's screen: `a_x²` in a grey box, typed rather than
    typeset."""
    from sensorlab.models import ContentBlock, Lab

    _seed()
    lab = Lab.objects.get(slug=LAB)
    for block in lab.content_blocks.filter(kind=ContentBlock.Kind.FORMULA):
        assert "\u00b2" not in block.body_en, "a superscript character is still typed by hand"
        assert "$$" in block.body_en, "the formula is not LaTeX"


def test_the_callout_no_longer_relies_on_inline_code():
    """Inline code inside Hebrew rendered as a mangled bidi mess on the
    phone. A formula belongs in maths, not in a code span."""
    from sensorlab.models import ContentBlock, Lab

    _seed()
    lab = Lab.objects.get(slug=LAB)
    for block in lab.content_blocks.filter(kind=ContentBlock.Kind.CALLOUT):
        assert "`" not in block.body_he, "the Hebrew callout still uses a code span"


def test_the_explanation_still_does_not_give_g_away_before_analysis():
    """SL-B3's content rule survives the rewrite. A much longer Learn step
    is exactly where the accepted value would slip back in."""
    from sensorlab.models import ContentBlock, Lab

    _seed()
    lab = Lab.objects.get(slug=LAB)
    before_analysis = lab.content_blocks.exclude(step=ContentBlock.Step.ANALYSIS)
    for block in before_analysis:
        for field in ("body_en", "body_he"):
            body = getattr(block, field)
            for spelled in ("9.81", "9.8 "):
                assert spelled not in body, (
                    f"block {block.pk}.{field} states g before the student measures it"
                )


# --------------------------------------------- maths never mirrors (§7.7)


def test_the_stylesheet_forces_maths_left_to_right():
    """Found by looking at the Hebrew Learn step.

    KaTeX inherited `direction: rtl` from the page and rendered
    `m g + F = m a` **backwards** — every display formula in the lab
    reversed. That is not a translation, it is wrong physics, and it is the
    sharpest case of §7.7 in the app: the chrome mirrors, the data does not,
    and an equation is data.
    """
    import re
    from pathlib import Path

    css = Path(__file__).resolve().parent.parent / "static" / "sensorlab" / "css" / "sensorlab.css"
    code = re.sub(r"/\*.*?\*/", "", css.read_text(encoding="utf-8"), flags=re.S)

    rule = re.search(r"\.katex[^{]*\{([^}]*)\}", code)
    assert rule, "nothing in the stylesheet addresses .katex at all"
    body = rule.group(1)
    assert "direction: ltr" in body, "maths is left to inherit the page direction"
    assert "unicode-bidi: isolate" in body, (
        "a formula inside a Hebrew sentence will disturb the words around it"
    )
