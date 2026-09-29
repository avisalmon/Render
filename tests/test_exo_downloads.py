"""exo — downloading the feature as a document (spec §5.4).

The thing worth testing here is not that a file comes back. It is that the two
formats need **opposite** treatment of the same Hebrew string, and that getting
that backwards produces a file which looks fine to every other assertion and is
unreadable to a person:

- Word does its own bidi, so the text must be stored in *logical* order with
  `w:bidi` set, and reordering it here would reverse it twice.
- ReportLab does none, so the text must be reordered *before* it is drawn.

memz lost a production day to this class of bug in both directions. These tests
are the cheap version of that lesson.
"""

import io
import re
import zipfile

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.urls import reverse

from exo import documents
from exo.access import approve, membership_for
from exo.models import Concept, NewspaperStyle, PressRelease

User = get_user_model()
pytestmark = pytest.mark.django_db

HEADLINE_HE = "שנה וחצי אחרי: מה קרה לחנות הפלאפל"
BODY_HE = (
    "בשתיים בצהריים, ביום שלישי רגיל, התור מגיע עד הפינה.\n\n"
    "\"בהתחלה חשבנו שזה יעבוד אחרת\", אומרת הבעלים.\n\n"
    "בתיה פקמן מגיעה שלוש פעמים בשבוע."
)


@pytest.fixture
def seeded():
    call_command("seed_exo", quiet=True)


@pytest.fixture
def owner(db):
    user = User.objects.create_user("owner", "o@example.com", "a-strong-pass-123")
    approve(membership_for(user, create=True))
    return user


def make_release(owner, **kw):
    concept = Concept.objects.create(owner=owner, title="חנות פלאפל",
                                     stage=Concept.Stage.OUTPUT)
    return PressRelease.objects.create(
        concept=concept,
        headline=kw.pop("headline", HEADLINE_HE),
        body=kw.pop("body", BODY_HE),
        document_body="המסמך המלא.",
        exponential_score=75,
        newspaper_style=NewspaperStyle.objects.first(),
        **kw,
    )


# ---- the two opposite bidi rules ---------------------------------------- #

def test_word_gets_logical_text_because_word_reorders_it_itself(seeded, owner):
    """Pre-reordering here would hand Word an already-reversed string to
    reverse again, which is the double-reversal bug this module exists to
    avoid."""
    release = make_release(owner)
    document = zipfile.ZipFile(
        io.BytesIO(documents.feature_docx(release))
    ).read("word/document.xml").decode("utf-8")

    assert HEADLINE_HE in document, "the text was reordered before Word saw it"
    assert documents._visual(HEADLINE_HE) not in document


def test_word_is_told_the_direction_rather_than_shown_it(seeded, owner):
    release = make_release(owner)
    document = zipfile.ZipFile(
        io.BytesIO(documents.feature_docx(release))
    ).read("word/document.xml").decode("utf-8")

    assert "<w:bidi/>" in document, "no paragraph direction: Word will guess"
    assert "<w:rtl/>" in document, "no run direction"
    assert '<w:jc w:val="right"/>' in document


def test_an_english_feature_is_not_marked_right_to_left(seeded, owner):
    release = make_release(owner, headline="Eighteen months on",
                           body="At two in the afternoon the queue reaches "
                                "the corner.\n\n\"It just works,\" she says.")
    document = zipfile.ZipFile(
        io.BytesIO(documents.feature_docx(release))
    ).read("word/document.xml").decode("utf-8")

    assert "<w:bidi/>" not in document
    assert '<w:jc w:val="left"/>' in document


def test_the_pdf_reorders_because_reportlab_will_not(seeded, owner):
    """The opposite rule. ReportLab draws glyphs in the order it is given, so
    the reordering has to happen before the draw call."""
    assert documents._visual(HEADLINE_HE) != HEADLINE_HE
    # Same characters, different order: a reordering, not a mangling.
    assert sorted(documents._visual(HEADLINE_HE)) == sorted(HEADLINE_HE)


def test_the_base_direction_is_pinned_not_guessed(seeded):
    """Auto-detection reads the first strong character and flips a whole
    paragraph for anything opening with a digit, an English word or a quote
    mark, all ordinary ways for one of these to begin."""
    opens_with_a_quote = '"בהתחלה חשבנו שזה יעבוד אחרת", אומרת הבעלים'
    shaped = documents._visual(opens_with_a_quote)
    assert shaped != opens_with_a_quote
    assert sorted(shaped) == sorted(opens_with_a_quote)


def test_direction_is_decided_by_the_text_not_by_a_setting(seeded):
    assert documents.is_rtl(HEADLINE_HE)
    assert not documents.is_rtl("Eighteen months on")
    assert documents.is_rtl("A shop called חנות פלאפל")


# ---- real files --------------------------------------------------------- #

def test_the_pdf_is_a_pdf_with_the_font_in_it(seeded, owner):
    release = make_release(owner)
    payload = documents.feature_pdf(release)
    assert payload.startswith(b"%PDF-")
    assert b"Heebo" in payload, "the Hebrew font was not embedded"
    assert len(payload) > 2000


def test_the_word_file_is_a_readable_archive(seeded, owner):
    release = make_release(owner)
    payload = documents.feature_docx(release)
    assert payload.startswith(b"PK")

    archive = zipfile.ZipFile(io.BytesIO(payload))
    assert archive.testzip() is None
    assert set(archive.namelist()) == {
        "[Content_Types].xml", "_rels/.rels", "word/document.xml",
    }
    # Word refuses a document whose XML does not parse, so parse it here.
    from xml.etree import ElementTree

    ElementTree.fromstring(archive.read("word/document.xml"))


def test_quotes_and_angle_brackets_do_not_break_the_document(seeded, owner):
    """A headline is full of quotes, and a feature can contain anything. XML
    that a stray `&` breaks is a file Word simply will not open."""
    release = make_release(
        owner,
        headline='הכתבה על "פלאפל & חברים" <הכי טוב>',
        body='הוא אמר: "זה & זה" <בדיוק>.\n\nועוד פסקה.',
    )
    archive = zipfile.ZipFile(io.BytesIO(documents.feature_docx(release)))
    from xml.etree import ElementTree

    ElementTree.fromstring(archive.read("word/document.xml"))
    documents.feature_pdf(release)  # must not raise either


# ---- the filename -------------------------------------------------------- #

def test_the_filename_is_the_headline(seeded, owner):
    release = make_release(owner)
    name = documents.filename_for(release, "pdf")
    assert name.endswith(".pdf")
    assert "פלאפל" in name


def test_a_filename_never_contains_something_a_filesystem_refuses(seeded, owner):
    release = make_release(owner, headline='a/b\\c:d*e?f"g<h>i|j')
    name = documents.filename_for(release, "docx")
    assert not re.search(r'[\\/:*?"<>|]', name)
    assert name.endswith(".docx")


def test_an_empty_headline_still_produces_a_usable_name(seeded, owner):
    release = make_release(owner, headline="")
    assert documents.filename_for(release, "pdf") == "exo.pdf"


# ---- the route ----------------------------------------------------------- #

def test_both_formats_download(client, seeded, owner):
    release = make_release(owner)
    for fmt, magic in [("pdf", b"%PDF-"), ("docx", b"PK")]:
        response = client.get(
            reverse("exo:article_download", args=[release.pk, fmt]))
        assert response.status_code == 200, fmt
        assert response.content.startswith(magic)
        assert "attachment" in response["Content-Disposition"]


def test_a_hebrew_filename_survives_the_header(client, seeded, owner):
    """A Hebrew name cannot travel in a plain `filename=`; RFC 5987's
    `filename*` is what carries it."""
    release = make_release(owner)
    response = client.get(reverse("exo:article_download", args=[release.pk, "pdf"]))
    disposition = response["Content-Disposition"]

    assert "filename*=UTF-8''" in disposition
    assert disposition.isascii(), "a raw Hebrew byte in a header breaks the download"


def test_an_unknown_format_is_not_offered(client, seeded, owner):
    release = make_release(owner)
    for fmt in ["exe", "txt", "html"]:
        response = client.get(
            reverse("exo:article_download", args=[release.pk, fmt]))
        assert response.status_code == 404, fmt


def test_a_private_feature_cannot_be_downloaded_by_a_stranger(client, seeded,
                                                              owner):
    """The same rule the museum page uses: guessing the number gets you
    nothing."""
    release = make_release(owner, visibility=PressRelease.Visibility.PRIVATE)
    assert client.get(
        reverse("exo:article_download", args=[release.pk, "pdf"])
    ).status_code == 404

    client.login(username="owner", password="a-strong-pass-123")
    assert client.get(
        reverse("exo:article_download", args=[release.pk, "pdf"])
    ).status_code == 200


def test_a_hidden_feature_cannot_be_downloaded(client, seeded, owner):
    release = make_release(owner, hidden_by_admin=True)
    assert client.get(
        reverse("exo:article_download", args=[release.pk, "pdf"])
    ).status_code == 404


def test_the_links_are_on_both_pages_the_article_is_read(client, seeded, owner):
    release = make_release(owner)
    pdf_url = reverse("exo:article_download", args=[release.pk, "pdf"])

    museum = client.get(reverse("exo:museum_item", args=[release.pk]))
    assert pdf_url in museum.content.decode(), "no download on the museum page"

    client.login(username="owner", password="a-strong-pass-123")
    output = client.get(
        reverse("exo:concept_output", args=[release.concept_id]))
    assert pdf_url in output.content.decode(), "no download on the output page"
