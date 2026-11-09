"""gallery, SPR-G.8: Avi's screens. Numbers, trainings, topics, people.

Sharpest: `test_counts_do_not_multiply` (methodology 20: three relations
counted on one row) and `test_unblocking_starts_clean_and_keeps_the_record`.

Traces: REQ-G.90 to G.94, G.61, G.62, G.73.
"""

from decimal import Decimal

import pytest
from django.contrib.auth.models import User
from django.utils import timezone

from gallery import skill_chat, skills
from gallery.access import ensure_person
from gallery.models import AICall, Exhibit, Person, Skill, SkillChat, Strike, Topic, Training

PASSWORD = "gallery-pass-5521"
GOOD = b"---\nname: excel-tables\ndescription: Builds Excel tables.\n---\n# Excel\n"
URLS = ["/gallery/manage/", "/gallery/manage/people/", "/gallery/manage/trainings/", "/gallery/manage/topics/"]


@pytest.fixture(autouse=True)
def quiet(settings, tmp_path):
    settings.GALLERY_FILES_DIR = tmp_path
    settings.GALLERY_SHOTS_ENABLED = False
    settings.OPENAI_API_KEY = ""  # methodology 26
    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
    settings.MAIL_GUARD_INNER_BACKEND = "django.core.mail.backends.locmem.EmailBackend"


def _person(email, training=None, other="", superuser=False, answered=True):
    user = User.objects.create_user(email, email, PASSWORD, first_name=email.split("@")[0])
    if superuser:
        user.is_superuser = user.is_staff = True
        user.save()
    p = ensure_person(user)
    if answered:
        p.training, p.training_other, p.training_set_at = training, other, timezone.now()
        p.save()
    return p


@pytest.fixture
def people(db):
    technion = Training.objects.get(name_en="Technion semester course")
    return {
        "dana": _person("dana@example.com", technion),
        "omer": _person("omer@example.com", other="a friend"),
        "noa": _person("noa@example.com", answered=False),
        "avi": _person("avi@example.com", superuser=True, answered=False),
        "technion": technion,
    }


def test_only_avi_sees_the_screens(client, people):
    for url in URLS + [f"/gallery/manage/people/{people['dana'].pk}/"]:
        assert client.get(url).status_code == 404
        client.force_login(people["dana"].user)
        assert client.get(url).status_code == 404
        assert client.post(url, {"action": "add", "name_en": "x"}).status_code == 404
        client.force_login(people["avi"].user)
        assert client.get(url).status_code == 200
        client.logout()
    assert not Training.objects.filter(name_en="x").exists()
    client.force_login(people["dana"].user)
    assert "/gallery/manage/" not in client.get("/gallery/").content.decode()
    client.force_login(people["avi"].user)
    assert 'href="/gallery/manage/"' in client.get("/gallery/").content.decode()


def test_counts_do_not_multiply(client, people):
    """REQ-G.93, G.94; methodology 20"""
    dana = people["dana"]
    for n in range(2):
        Exhibit.objects.create(owner=dana, title=f"p{n}", url="https://x.io/", kind=Exhibit.PAGE)
    chat, bundle, _ = skills.start(dana, "SKILL.md", GOOD)
    skills.publish(chat, bundle)
    for n in range(3):
        AICall.objects.create(person=dana, chat=chat, purpose="safety", model="gpt-6-luna", cost_usd=Decimal("0.0010"))
    Strike.objects.create(person=dana, chat=chat, findings="x")
    client.force_login(people["avi"].user)
    page = client.get("/gallery/manage/people/").content.decode()
    row = page[page.index("dana@example.com"):page.index("</tr>", page.index("dana@example.com"))]
    cells = [c.strip() for c in row.split("<td")[1:]]
    assert [c.split(">", 1)[1].split("<")[0] for c in cells[1:5]] == ["2", "1", "1", "$0.0030"]


def test_numbers_by_training(client, people):
    """REQ-G.94"""
    Exhibit.objects.create(owner=people["dana"], title="a", url="https://x.io/")
    Exhibit.objects.create(owner=people["omer"], title="b", url="https://x.io/")
    AICall.objects.create(person=people["omer"], purpose="safety", model="gpt-6-luna", cost_usd=Decimal("0.0200"))
    SkillChat.objects.create(person=people["omer"], status=SkillChat.OUT_OF_BUDGET, cost_usd=Decimal("0.39"))
    client.force_login(people["avi"].user)
    page = client.get("/gallery/manage/").content.decode()
    table = page[page.index('id="gl-by-training"'):page.index("</table>", page.index('id="gl-by-training"'))]
    technion = table[table.index(people["technion"].name_he):]
    assert "<td>1</td><td>1</td><td>0</td>" in technion.split("</tr>")[0]
    other = table[table.index("<td>אחר</td>"):].split("</tr>")[0]
    assert "<td>1</td><td>1</td><td>0</td>" in other and "$0.0200" in other
    assert "a friend" in page  # what "other" people wrote
    assert 'id="gl-no-ceiling"' not in page and "$0.39" in page
    assert "$0.0200" in page[page.index('id="gl-top-cost"'):]


def test_trainings_add_edit_close_reorder(client, people):
    """REQ-G.91"""
    client.force_login(people["avi"].user)
    client.post("/gallery/manage/trainings/", {"action": "add", "name_he": "סדנה באריאל", "name_en": "Ariel workshop"})
    t = Training.objects.get(name_en="Ariel workshop")
    assert t.is_open and t.position == max(Training.objects.values_list("position", flat=True))
    client.post("/gallery/manage/trainings/", {"action": "save", "pk": t.pk, "name_he": "סדנה באריאל 2026", "name_en": "Ariel 2026"})
    t.refresh_from_db()
    assert (t.name_he, t.name_en) == ("סדנה באריאל 2026", "Ariel 2026")
    client.post("/gallery/manage/trainings/", {"action": "up", "pk": t.pk})
    assert list(Training.objects.values_list("pk", flat=True))[-2] == t.pk
    technion = people["technion"]
    client.post("/gallery/manage/trainings/", {"action": "toggle", "pk": technion.pk})
    technion.refresh_from_db()
    assert not technion.is_open and Person.objects.get(pk=people["dana"].pk).training == technion
    client.force_login(people["noa"].user)
    assert technion.name_he not in client.get("/gallery/training/").content.decode()


def test_topics_add_edit(client, people):
    """REQ-G.92"""
    client.force_login(people["avi"].user)
    client.post("/gallery/manage/topics/", {"action": "add", "name_he": "אבטחה", "name_en": "Security"})
    t = Topic.objects.get(slug="security")
    page = client.post("/gallery/manage/topics/", {"action": "add", "name_he": "x", "name_en": "Security"}).content.decode()
    assert Topic.objects.filter(slug="security").count() == 1 and "gl-error" in page
    client.post("/gallery/manage/topics/", {"action": "save", "pk": t.pk, "name_he": "אבטחת מידע", "name_en": "Security"})
    t.refresh_from_db()
    assert t.name_he == "אבטחת מידע" and t.slug == "security"
    client.force_login(people["dana"].user)
    assert "אבטחת מידע" in client.get("/gallery/new/").content.decode()


def test_unlimited_and_reset_updates(client, people):
    """REQ-G.61, G.62"""
    dana = people["dana"]
    chat, bundle, _ = skills.start(dana, "SKILL.md", GOOD)
    skill = skills.publish(chat, bundle)
    chat, bundle, _ = skills.start(dana, "SKILL.md", GOOD.replace(b"excel-tables", b"word-letters"))
    skills.publish(chat, bundle)
    assert skills.may_start(dana)[0] is False
    client.force_login(people["avi"].user)
    client.post("/gallery/manage/people/", {"action": "unlimited", "pk": dana.pk})
    assert skills.may_start(Person.objects.get(pk=dana.pk)) == (True, "")
    Skill.objects.filter(pk=skill.pk).update(updates_used=4)
    client.post("/gallery/manage/people/", {"action": "reset_updates", "skill": skill.pk})
    assert Skill.objects.get(pk=skill.pk).updates_used == 0


def test_unblocking_starts_clean_and_keeps_the_record(client, people):
    """REQ-G.73"""
    dana = people["dana"]
    for _ in range(2):
        chat = SkillChat.objects.create(person=dana)
        skill_chat._strike(chat, "sends keys out", "en")
    dana.refresh_from_db()
    assert dana.skills_blocked_at
    client.force_login(people["avi"].user)
    page = client.get(f"/gallery/manage/people/{dana.pk}/").content.decode()
    assert 'id="gl-unblock"' in page and "sends keys out" in page
    client.post("/gallery/manage/people/", {"action": "unblock", "pk": dana.pk, "back": f"/gallery/manage/people/{dana.pk}/"})
    dana.refresh_from_db()
    assert dana.skills_blocked_at is None and skills.may_start(dana) == (True, "")
    assert Strike.objects.filter(person=dana).count() == 2  # the record stays
    # One more risky upload is a first strike again, not an instant block.
    skill_chat._strike(SkillChat.objects.create(person=dana), "again", "en")
    dana.refresh_from_db()
    assert dana.skills_blocked_at is None


def test_back_cannot_leave_the_site(client, people):
    client.force_login(people["avi"].user)
    r = client.post("/gallery/manage/people/", {"action": "unlimited", "pk": people["dana"].pk, "back": "https://evil.example/"})
    assert r.status_code == 302 and not r["Location"].startswith("http")
