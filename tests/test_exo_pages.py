"""exo — every page renders, in both languages (spec §0.3, §13).

This app is roughly twenty-five templates and two languages, which is fifty
renders no single feature test ever performs. The failure this catches is the
quiet one: a template that only breaks once real data reaches it, or a string
key that renders as `nav.buld` because of a typo nobody saw in Hebrew.

`{% t %}` returns the key itself when it is missing (strings.py), so an
untranslated string is visible in the HTML as a dotted key, and this file
treats that as a failure rather than a cosmetic problem.
"""

import re

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.urls import reverse
from django.utils import timezone

from exo.access import approve, membership_for
from exo.models import (
    BrainstormEntry,
    Concept,
    ExoAttribute,
    GeneratedOption,
    LearnResource,
    NewspaperStyle,
    PressRelease,
)

User = get_user_model()
pytestmark = pytest.mark.django_db

LANGUAGES = ["he", "en"]

#: A dotted lowercase token sitting alone in text is what an unresolved
#: `{% t %}` looks like. Anchored to the string table's own prefixes so a
#: filename or a version number in the copy is not mistaken for one.
LEAKED_KEY = re.compile(
    r">\s*((?:nav|home|learn|museum|stage|build|join|manage|output|options|"
    r"brainstorm|interview|lang|footer|error|action|status)\.[a-z_.]+)\s*<"
)


@pytest.fixture
def world(db):
    """One of everything, so the pages render with real rows rather than the
    empty state only."""
    call_command("seed_exo", quiet=True)

    owner = User.objects.create_user("owner", "owner@example.com",
                                     "a-strong-pass-123")
    approve(membership_for(owner, create=True))
    admin = User.objects.create_superuser("root", "root@example.com",
                                          "a-strong-pass-123")

    # Someone waiting, so the cockpit has a row to draw.
    waiting = User.objects.create_user("waiting", "w@example.com",
                                       "a-strong-pass-123")
    membership_for(waiting, create=True)

    concept = Concept.objects.create(owner=owner, title="A car rental service",
                                     stage=Concept.Stage.OUTPUT,
                                     mtp="Movement without ownership")
    attribute = ExoAttribute.objects.get(key="algorithms")
    BrainstormEntry.objects.create(concept=concept, attribute=attribute,
                                   text="predict demand per street")
    GeneratedOption.objects.create(concept=concept, attribute=attribute,
                                   content="a demand model per street",
                                   research_note="a note", is_selected=True)
    concept.messages.create(role="assistant", content="What are you building?",
                            order=1)
    concept.messages.create(role="user", content="A car rental service", order=2)

    release = PressRelease.objects.create(
        concept=concept, headline="Cars arrive before you ask",
        body="A press release body.", document_body="A longer document.",
        exponential_score=61, score_rationale="Because.",
        newspaper_style=NewspaperStyle.objects.first(),
    )
    return {"owner": owner, "admin": admin, "concept": concept,
            "release": release, "attribute": attribute}


def public_urls(world):
    page = LearnResource.objects.filter(attribute__isnull=True).first()
    return [
        reverse("exo:home"),
        reverse("exo:learn"),
        reverse("exo:learn_page", args=[page.key]),
        reverse("exo:learn_attribute", args=[world["attribute"].key]),
        reverse("exo:museum"),
        reverse("exo:museum_item", args=[world["release"].pk]),
        reverse("exo:join"),
        reverse("exo:login"),
    ]


def member_urls(world):
    pk = world["concept"].pk
    return [
        reverse("exo:concepts"),
        reverse("exo:concept_interview", args=[pk]),
        reverse("exo:concept_brainstorm", args=[pk]),
        reverse("exo:concept_options", args=[pk]),
        reverse("exo:concept_output", args=[pk]),
    ]


def admin_urls(world):
    return [
        reverse("exo:manage_requests"),
        reverse("exo:manage_releases"),
        reverse("exo:manage_usage"),
    ]


def render_in(client, url, language):
    client.get(reverse("exo:set_language", args=[language]))
    return client.get(url)


def check(response, url, language):
    assert response.status_code == 200, f"{url} [{language}] -> {response.status_code}"
    html = response.content.decode()
    assert f'lang="{language}"' in html, f"{url} [{language}] wrong lang attribute"
    expected_dir = "rtl" if language == "he" else "ltr"
    assert f'dir="{expected_dir}"' in html, f"{url} [{language}] wrong direction"
    leaked = LEAKED_KEY.findall(html)
    assert not leaked, f"{url} [{language}] shows untranslated keys: {leaked}"


# ---- the page says what it is about ------------------------------------ #
#
# Added after the render walk passed a page whose heading was empty. Every
# template wrote `{% tr a "name_en" %}`, which asks the tag for a field called
# `name_en_he`, gets nothing, and renders a blank <h1> — a 200 with no title on
# it, in five templates, which every structural assertion sailed past. Status
# codes and language attributes are not enough: a page has to *say* something.


def test_an_attribute_page_actually_names_its_attribute(client, world):
    """Checked in the `<h1>`, not anywhere in the document.

    The first version of this test asserted the name appeared in the HTML at
    all, and passed happily on a page whose heading was empty — because the
    same name sits in the `<title>` tag. A test that a broken page satisfies is
    not a test."""
    import re as _re

    attribute = world["attribute"]
    url = reverse("exo:learn_attribute", args=[attribute.key])
    heading = _re.compile(r"<h1[^>]*>(.*?)</h1>", _re.S)

    client.get(reverse("exo:set_language", args=["he"]))
    html = client.get(url).content.decode()
    assert attribute.name_he in heading.search(html).group(1)
    # The English term sits above the Hebrew title, because that is the word
    # people will hear said out loud in the room.
    assert attribute.name_en in html

    client.get(reverse("exo:set_language", args=["en"]))
    html = client.get(url).content.decode()
    assert attribute.name_en in heading.search(html).group(1)


def test_the_handout_lists_every_attribute_by_name(client, world):
    """The index of the whole handout. A blank row here is the page telling
    thirteen lies at once.

    Compared against the escaped name: "Community & Crowd" reaches the browser
    as `Community &amp; Crowd`, and a test that did not know that would fail on
    a page that is perfectly correct."""
    from django.utils.html import escape

    for language in LANGUAGES:
        client.get(reverse("exo:set_language", args=[language]))
        html = client.get(reverse("exo:learn")).content.decode()
        for attribute in ExoAttribute.objects.all():
            name = escape(attribute.tr("name", language))
            assert name in html, f"{attribute.key} is nameless in {language}"


def test_no_heading_anywhere_renders_empty(client, world):
    """The general form of the same bug: an h1 or h2 with nothing in it.

    Cheap to check, and it covers the templates this suite has not thought to
    name yet."""
    import re as _re

    client.login(username="owner", password="a-strong-pass-123")
    empty = _re.compile(r"<(?:h1|h2)[^>]*>\s*</(?:h1|h2)>")
    urls = public_urls(world) + member_urls(world)
    for language in LANGUAGES:
        client.get(reverse("exo:set_language", args=[language]))
        for url in urls:
            html = client.get(url).content.decode()
            assert not empty.search(html), f"empty heading on {url} [{language}]"


# ---- the detector has to be able to fail ------------------------------- #

def test_the_untranslated_key_detector_actually_catches_one():
    """A guard that can never fire is worse than no guard, because it reads
    like coverage. This proves the pattern sees a leak and ignores ordinary
    copy."""
    leak = '<a href="/x">nav.buld</a><span> home.lede </span>'
    assert LEAKED_KEY.findall(leak) == ["nav.buld", "home.lede"]

    ordinary = '<a href="/x">Learn</a><p>exo.css</p><span>version 1.2.3</span>'
    assert LEAKED_KEY.findall(ordinary) == []


# ---- the walk ---------------------------------------------------------- #

@pytest.mark.parametrize("language", LANGUAGES)
def test_every_public_page_renders(client, world, language):
    for url in public_urls(world):
        check(render_in(client, url, language), url, language)


@pytest.mark.parametrize("language", LANGUAGES)
def test_every_builder_page_renders(client, world, language):
    client.login(username="owner", password="a-strong-pass-123")
    for url in member_urls(world):
        check(render_in(client, url, language), url, language)


@pytest.mark.parametrize("language", LANGUAGES)
def test_every_cockpit_page_renders(client, world, language):
    client.login(username="root", password="a-strong-pass-123")
    for url in admin_urls(world):
        check(render_in(client, url, language), url, language)


@pytest.mark.parametrize("language", LANGUAGES)
def test_the_waiting_and_denied_screens_render(client, world, language):
    from exo.models import Membership

    client.login(username="waiting", password="a-strong-pass-123")
    check(render_in(client, reverse("exo:waiting"), language),
          "waiting", language)

    membership = User.objects.get(username="waiting").exo_membership
    membership.status = Membership.Status.DENIED
    membership.save()
    client.get(reverse("exo:set_language", args=[language]))
    response = client.get(reverse("exo:concepts"))
    assert response.status_code == 403
    assert f'lang="{language}"' in response.content.decode()


# ---- the empty states, which is what a new person actually sees --------- #

@pytest.mark.parametrize("language", LANGUAGES)
def test_the_empty_states_render(client, db, language):
    """A first visit before anything exists: an empty museum and a builder with
    no concepts. These are the screens a workshop opens on."""
    call_command("seed_exo", quiet=True)
    user = User.objects.create_user("fresh", "f@example.com", "a-strong-pass-123")
    approve(membership_for(user, create=True))
    client.login(username="fresh", password="a-strong-pass-123")

    for url in [reverse("exo:museum"), reverse("exo:concepts")]:
        check(render_in(client, url, language), url, language)


@pytest.mark.parametrize("language", LANGUAGES)
def test_a_concept_at_every_stage_renders(client, db, language):
    """Each stage drawn at its own beginning, with nothing filled in yet, since
    that is the state each screen is first seen in."""
    call_command("seed_exo", quiet=True)
    user = User.objects.create_user("stager", "s@example.com", "a-strong-pass-123")
    approve(membership_for(user, create=True))
    client.login(username="stager", password="a-strong-pass-123")

    for stage, name in [
        (Concept.Stage.INTERVIEW, "exo:concept_interview"),
        (Concept.Stage.BRAINSTORM, "exo:concept_brainstorm"),
        (Concept.Stage.OPTIONS, "exo:concept_options"),
        (Concept.Stage.OUTPUT, "exo:concept_output"),
    ]:
        concept = Concept.objects.create(owner=user, title="bare", stage=stage)
        url = reverse(name, args=[concept.pk])
        check(render_in(client, url, language), url, language)


# ---- the newspaper ------------------------------------------------------ #

def test_every_newspaper_style_renders(client, world):
    """Five papers, each with its own class and its own stylesheet rules. A
    style that renders blank is invisible until someone picks it in a workshop
    (spec §6.3). Looped rather than parametrized, because the list of styles
    lives in the database and pytest builds parameters before it exists."""
    release = world["release"]
    styles = list(NewspaperStyle.objects.all())
    assert len(styles) == 5

    for style in styles:
        release.newspaper_style = style
        release.save(update_fields=["newspaper_style"])

        response = client.get(reverse("exo:museum_item", args=[release.pk]))
        assert response.status_code == 200, style.key
        html = response.content.decode()
        assert style.css_class in html, style.key
        assert release.headline in html, style.key


# ---- the error pages, in exo's own chrome ------------------------------- #

@pytest.mark.parametrize("language", LANGUAGES)
def test_the_404_wears_exo_chrome_not_the_sites(client, world, language):
    client.get(reverse("exo:set_language", args=[language]))
    response = client.get("/exo/learn/no-such-thing/")
    assert response.status_code == 404
    html = response.content.decode()
    assert f'lang="{language}"' in html
    assert "exo" in html


# ---- the expired release still opens for its owner ---------------------- #

def test_an_expired_release_renders_for_its_owner(client, world):
    release = world["release"]
    release.visibility = PressRelease.Visibility.TIMED
    release.public_until = timezone.now() - timezone.timedelta(hours=1)
    release.save()
    client.login(username="owner", password="a-strong-pass-123")
    response = client.get(reverse("exo:museum_item", args=[release.pk]))
    assert response.status_code == 200
