"""BK9: discovery (docs/books/backlog.md, spec BK9). The tagging model and
its limits, taste from the survey and from a person's books, explainable
recommendations, near-you first, more by the author, readers also read
(only from three people up, never named). Refusals and privacy first."""

import json
from decimal import Decimal
from types import SimpleNamespace

import pytest
from django.contrib.auth import get_user_model

from books import catalog, circles, community, discover, jobs, storage, tagging
from books.models import (CatalogEntry, Copy, EntryTagging, Job, ModelCall, Offer, Profile, ProfileTaste, Tag)

pytestmark = [pytest.mark.sprbk9, pytest.mark.django_db]
User = get_user_model()


@pytest.fixture(autouse=True)
def _env(settings, tmp_path, monkeypatch):
    settings.MEDIA_ROOT = str(tmp_path)
    settings.BOOKS_GCS_BUCKET = ""
    settings.BOOKS_JOBS_INLINE = True
    settings.OPENAI_API_KEY = ""
    storage.reset_for_tests()
    monkeypatch.setattr(catalog, "lookup", lambda **kw: [])
    from django.core.cache import cache

    cache.clear()
    from django.core.management import call_command

    call_command("seed_books", verbosity=0)
    yield
    storage.reset_for_tests()


def person(name, email):
    u = User.objects.create_user(email.split("@")[0], email, "pw")
    return Profile.objects.create(user=u, display_name=name, is_adult_confirmed=True, area_name="הדר")


@pytest.fixture
def noa(db):
    return person("נועה", "noa@example.com")


def book(title, author="", *tag_keys):
    e = CatalogEntry.objects.create(collection_type=catalog.book_type(), title=title)
    if author:
        catalog.set_creators(e, [author])
    e.tags.add(*Tag.objects.filter(key__in=tag_keys))
    return e


def login(client, p):
    client.force_login(p.user)
    return client


class FakeClient:
    def __init__(self, answer):
        self.answer = answer
        self.calls = []
        self.responses = SimpleNamespace(create=self._create)

    def _create(self, **kw):
        self.calls.append(kw)
        return SimpleNamespace(output_text=json.dumps(self.answer),
                               usage=SimpleNamespace(input_tokens=900, output_tokens=60))


# ---- refusals and privacy ---------------------------------------------------------------------

def test_signed_out_people_get_no_suggestions(client):
    for url in ("/books/discover/", "/books/taste/", "/books/api/discover/"):
        assert client.get(url).status_code in (302, 403)


def test_readers_also_read_needs_three_people_and_never_names_them(client, noa):
    target = book("מיכאל שלי", "עמוס עוז", "literary-fiction")
    other = book("סיפור על אהבה וחושך", "עמוס עוז", "biography")
    readers = [person(f"קורא {i}", f"r{i}@example.com") for i in range(3)]
    for r in readers[:2]:
        Copy.objects.create(owner=r, entry=target)
        community.log_reading(r, other, "read")
    assert discover.also_read(target, noa) == []  # two people are not enough
    Copy.objects.create(owner=readers[2], entry=target)
    community.log_reading(readers[2], other, "read")
    rows = discover.also_read(target, noa)
    assert [(r["entry"], r["people"]) for r in rows] == [(other, 3)]
    page = login(client, noa).get(f"/books/catalog/{target.pk}/").content.decode()
    assert "סיפור על אהבה וחושך" in page and "3 קוראים" in page
    assert not any(r.display_name in page for r in readers)
    # One of the three is me: then only two others, and it disappears.
    assert discover.also_read(target, readers[0]) == []


def test_my_taste_is_mine_alone(client, noa):
    dan = person("דן", "dan@example.com")
    discover.set_survey(dan, ["fantasy"], ["thriller"])
    login(client, noa)
    assert client.get("/books/api/discover/taste/").json() == []
    assert ' checked>' not in client.get("/books/taste/").content.decode()  # nothing of dan's is ticked for noa
    assert ProfileTaste.objects.filter(profile=dan).count() == 2


def test_the_model_can_only_set_tags_from_the_list_and_never_form(noa):
    e = book("Dune", "Frank Herbert")
    tagging.apply(e, {"genre": ["science-fiction", "made-up-genre"], "mood": ["tense"], "audience": ["adults"],
                      "form": ["signed"], "confidence": 0.9}, "fake")
    assert set(e.tags.values_list("key", flat=True)) == {"science-fiction", "tense", "adults"}


def test_an_unsure_answer_is_kept_for_audit_but_not_applied(noa):
    e = book("ספר לא מוכר", "")
    tagging.apply(e, {"genre": ["romance"], "mood": [], "audience": [], "confidence": 0.2}, "fake")
    assert not e.tags.exists()
    assert EntryTagging.objects.get(entry=e).raw["genre"] == ["romance"]


def test_a_curators_tags_are_never_overwritten(client, noa):
    staff = person("אבי", "avi@example.com")
    staff.user.is_staff = True
    staff.user.save()
    e = book("Dune", "Frank Herbert")
    login(client, staff).post(f"/books/catalog/{e.pk}/edit/", {
        "title": "Dune", "subtitle": "", "creators": "Frank Herbert", "language": "en", "year": "",
        "publisher": "", "identifier": "", "tags": [Tag.objects.get(key="classics").pk]})
    assert EntryTagging.objects.get(entry=e).source == EntryTagging.CURATOR
    tagging.apply(e, {"genre": ["romance"], "mood": [], "audience": [], "confidence": 0.99}, "fake")
    assert set(e.tags.values_list("key", flat=True)) == {"classics"}


def test_no_key_no_tagging_and_never_twice_a_day(settings, noa, monkeypatch):
    e = book("Dune")
    assert tagging.ensure_tagged(e, noa) is False  # no key in this environment
    settings.OPENAI_API_KEY = "sk-test"
    started = []
    monkeypatch.setattr(jobs, "enqueue", lambda kind, **kw: started.append(kind) or Job.objects.create(
        kind=kind, ref_id=kw.get("ref_id")))
    assert tagging.ensure_tagged(e, noa) is True
    assert tagging.ensure_tagged(e, noa) is False
    assert started == ["entry.tag"]


# ---- tagging ----------------------------------------------------------------------------------------

def test_the_tag_job_asks_once_records_the_cost_and_applies(noa, monkeypatch):
    e = book("הארי פוטר ואבן החכמים", "ג'יי קיי רולינג")
    fake = FakeClient({"genre": ["fantasy"], "mood": ["hopeful"], "audience": ["children"], "confidence": 0.97})
    monkeypatch.setattr(tagging, "get_client", lambda: fake)
    row = Job.objects.create(kind="entry.tag", ref_id=e.pk, profile=noa)
    jobs.run(row.pk)
    assert set(e.tags.values_list("key", flat=True)) == {"fantasy", "hopeful", "children"}
    call = ModelCall.objects.get(purpose="entry_tag")
    assert call.model == "gpt-6-luna" and call.cost_usd > 0 and call.profile == noa
    schema = fake.calls[0]["text"]["format"]["schema"]
    assert set(schema["properties"]) == {"genre", "mood", "audience", "confidence"}
    assert "fantasy" in schema["properties"]["genre"]["items"]["enum"]


# ---- taste and suggestions --------------------------------------------------------------------------

def test_onboarding_ends_at_the_survey_which_can_be_skipped(client):
    u = User.objects.create_user("fresh", "fresh@example.com", "pw")
    client.force_login(u)
    r = client.post("/books/welcome/?next=/books/near/", {"display_name": "חדש", "language": "he", "area_name": "",
                                                          "is_adult_confirmed": "on", "accept_terms": "on"})
    assert r["Location"].startswith("/books/taste/?first=1")
    page = client.get(r["Location"]).content.decode()
    assert 'name="skip"' in page
    r = client.post("/books/taste/", {"first": "1", "skip": "1", "next": "/books/near/"})
    assert r["Location"] == "/books/near/"
    r = client.post("/books/taste/", {"like": ["fantasy", "hopeful"], "dislike": ["thriller"], "next": ""})
    me = Profile.objects.get(user=u)
    assert {(t.tag.key, float(t.weight)) for t in me.taste.all()} == {("fantasy", 1.0), ("hopeful", 1.0),
                                                                       ("thriller", -1.0)}


def test_suggestions_follow_taste_say_why_and_skip_what_i_have(client, noa):
    liked = book("הארי פוטר", "ג'יי קיי רולינג", "fantasy", "hopeful")
    match = book("ההוביט", "J.R.R. Tolkien", "fantasy")
    tense = book("מותחן", "", "thriller")
    mixed = book("פנטזיה מותחת", "", "fantasy", "thriller")
    mine = book("פנטזיה שכבר יש לי", "", "fantasy")
    Copy.objects.create(owner=noa, entry=mine)
    community.set_review(noa, liked, 5)
    discover.set_survey(noa, ["fantasy"], ["thriller"])
    discover.derive(noa)
    recs = discover.for_you(noa)
    titles = [r["entry"].title for r in recs]
    assert "ההוביט" in titles and "מותחן" not in titles and "פנטזיה שכבר יש לי" not in titles
    assert "הארי פוטר" not in titles  # reviewed: already seen
    hobbit = next(r for r in recs if r["entry"] == match)
    assert hobbit["because"] == liked and [t.key for t in hobbit["tags"]] == ["fantasy"]
    assert titles.index("ההוביט") < titles.index("פנטזיה מותחת")  # the disliked tag pulls it down
    page = login(client, noa).get("/books/discover/").content.decode()
    assert "ההוביט" in page and "כמו ״הארי פוטר״" in page and "פנטזיה" in page


def test_what_is_offered_near_me_comes_first(client, noa):
    discover.set_survey(noa, ["fantasy"])
    far_off = book("ספר רחוק", "", "fantasy")
    nearby = book("ספר קרוב", "", "fantasy")
    owner = person("דן", "dan@example.com")
    c = Copy.objects.create(owner=owner, entry=nearby, visibility=Copy.PUBLIC)
    Offer.objects.create(copy=c, kind="lend", loan_days=30)
    recs = discover.for_you(noa)
    assert recs[0]["entry"] == nearby and recs[0]["near"] is True
    assert discover.available_near(nearby, noa) == 1 and discover.available_near(far_off, noa) == 0
    page = login(client, noa).get("/books/discover/").content.decode()
    near_h, more_h = page.index("בשבילך, ומוצע בקרבתך"), page.index("עוד בשבילך")
    assert near_h < page.index("ספר קרוב") < more_h < page.index("ספר רחוק")
    entry_page = client.get(f"/books/catalog/{nearby.pk}/").content.decode()
    assert "1 עותקים מוצעים בקרבתך" in entry_page


def test_derived_taste_comes_from_my_own_books_and_reviews(noa):
    good = book("טוב", "", "fantasy")
    bad = book("רע", "", "romance")
    community.set_review(noa, good, 5)
    community.set_review(noa, bad, 1)
    discover.derive(noa)
    t = {r.tag.key: float(r.weight) for r in ProfileTaste.objects.filter(profile=noa, source="derived")}
    assert t["fantasy"] > 0 > t["romance"]


def test_more_by_the_author_and_my_circles_favourites(client, noa):
    a = book("מיכאל שלי", "עמוס עוז")
    b = book("סיפור על אהבה וחושך", "עמוס עוז")
    c = book("ספר אחר", "מישהו")
    assert discover.more_by_author(a, noa) == [b]
    club = circles.create(noa, "מועדון")
    for i in range(2):
        p = person(f"חבר {i}", f"m{i}@example.com")
        circles.join(p, club, club.join_code)
        Copy.objects.create(owner=p, entry=c, visibility=Copy.PUBLIC)
    rows = discover.popular_in_circles(noa)
    assert [(r["entry"], r["people"]) for r in rows] == [(c, 2)]
    assert "עוד מאותו סופר/ת" in login(client, noa).get(f"/books/catalog/{a.pk}/").content.decode()


def test_the_discover_page_starts_tagging_my_untagged_books(client, noa, settings, monkeypatch):
    settings.OPENAI_API_KEY = "sk-test"
    e = book("ספר בלי תגים")
    Copy.objects.create(owner=noa, entry=e)
    fake = FakeClient({"genre": ["fiction"], "mood": [], "audience": [], "confidence": 0.9})
    monkeypatch.setattr(tagging, "get_client", lambda: fake)
    login(client, noa).get("/books/discover/")
    assert set(e.tags.values_list("key", flat=True)) == {"fiction"}
    assert client.get("/books/api/discover/").status_code == 200
    r = client.post("/books/api/discover/taste/", {"like": ["fiction"]})
    assert r.json()[0]["tag"] in {"fiction"}
    assert client.get(f"/books/api/discover/entry/?id={e.pk}").json()["near_count"] == 0
    assert Decimal(str(ModelCall.objects.get().cost_usd)) > 0


def test_the_survey_offers_every_genre_and_shows_my_answers(client, noa):
    """Found on the screenshot: only top-level genres were offered, so a saved
    "fantasy" (under prose) could neither be chosen nor seen."""
    discover.set_survey(noa, ["fantasy"], ["thriller"])
    page = login(client, noa).get("/books/taste/").content.decode()
    for tag in Tag.objects.filter(kind__in=["genre", "mood"]):
        assert f'value="{tag.key}"' in page, tag.key
    assert 'name="like" value="fantasy" checked>' in page
    assert 'name="dislike" value="thriller" checked>' in page
