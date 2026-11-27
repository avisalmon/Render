"""breakout B.5.1: two levels past the teachers' door (Avi, 2026-11-27:
"which teacher may only view and download, and which may create").

A teacher approved as a viewer reads, prepares and prints and cannot write,
on the screens or through the API; approved as a creator, the editor and
the API open. A curator chooses the level at approval and may promote or
demote at any time; the API tells the level and lets nobody set it.
"""

import re

import pytest
from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import Client

from breakout import access
from breakout.models import Experience, Profile

pytestmark = [pytest.mark.breakout, pytest.mark.django_db]

PASSWORD = "paper-rooms-2211"
FLAGSHIP = "hamachshev-shenichba"


@pytest.fixture
def avi(db):
    return User.objects.create_superuser("avi", "avi@example.com", PASSWORD, first_name="אבי")


@pytest.fixture
def dana(db):
    """Approved as a viewer: the default level."""
    user = User.objects.create_user("dana", "dana@example.com", PASSWORD, first_name="דנה")
    profile = access.profile_for(user)
    profile.is_teacher = True
    profile.save()
    return user


@pytest.fixture
def asker(db):
    """Signed in, asked, waits at the door."""
    user = User.objects.create_user("noa", "noa@example.com", PASSWORD, first_name="נועה")
    profile = access.profile_for(user)
    profile.school, profile.teaches, profile.asked_at = "תיכון הנגב", "מדעי המחשב", profile.joined_at
    profile.save()
    return user


@pytest.fixture
def seeded(avi):
    call_command("seed_breakout", verbosity=0)
    return Experience.objects.get(slug=FLAGSHIP)


def _as(user):
    c = Client()
    c.force_login(user)
    return c


def _ul(html, element_id):
    return re.search(rf'<ul class="br-people" id="{element_id}">(.*?)</ul>', html, re.S).group(1)


NEW_EXPERIENCE = {"title": "אתגר של דנה", "slug": "new-room", "tagline": "שורה אחת", "story": "פעם", "audience_from": 7, "audience_to": 9}


def test_a_viewer_reads_and_prints_and_cannot_write(seeded, dana):
    c = _as(dana)
    assert c.get(f"/breakout/x/{FLAGSHIP}/prep/").status_code == 200
    assert c.get(f"/breakout/x/{FLAGSHIP}/print/plain/?groups=1")["Content-Type"] == "application/pdf"
    assert "כתיבת אתגר" not in c.get("/breakout/").content.decode()
    assert c.get("/breakout/new/").status_code == 404
    r = c.post("/breakout/api/experiences/", NEW_EXPERIENCE, content_type="application/json")
    assert r.status_code == 403
    assert Experience.objects.filter(author=dana).count() == 0
    assert access.may_write(dana) is False


def test_a_curator_approves_as_a_viewer_or_as_a_creator(seeded, avi, asker):
    c = _as(avi)
    pending = _ul(c.get("/breakout/curators/teachers/").content.decode(), "br-pending")
    assert 'value="approve"' in pending and 'value="approve_creator"' in pending and 'value="decline"' in pending
    profile = access.profile_for(asker)
    assert c.post(f"/breakout/curators/teachers/{profile.pk}/", {"action": "approve_creator"}).status_code == 302
    profile.refresh_from_db()
    assert profile.is_teacher and profile.is_creator
    assert profile.teacher_by == avi and profile.creator_by == avi and profile.creator_since is not None
    # The creator is in, and may write: the button, the editor, the API.
    me = _as(asker)
    assert "כתיבת אתגר" in me.get("/breakout/").content.decode()
    assert me.get("/breakout/new/").status_code == 200
    r = me.post("/breakout/api/experiences/", NEW_EXPERIENCE, content_type="application/json")
    assert r.status_code == 201, r.content
    exp = Experience.objects.get(author=asker)
    assert exp.status == Experience.DRAFT
    # The page shows the level.
    approved = _ul(c.get("/breakout/curators/teachers/").content.decode(), "br-approved")
    assert "נועה" in approved and 'br-tag--creator">יוצר/ת' in approved and 'value="demote"' in approved


def test_a_curator_promotes_and_demotes_at_any_time(seeded, avi, dana, asker):
    c = _as(avi)
    dana_profile = access.profile_for(dana)
    approved = _ul(c.get("/breakout/curators/teachers/").content.decode(), "br-approved")
    assert '<span class="br-tag">צופה</span>' in approved and 'value="promote"' in approved
    c.post(f"/breakout/curators/teachers/{dana_profile.pk}/", {"action": "promote"})
    dana_profile.refresh_from_db()
    assert dana_profile.is_creator and dana_profile.creator_by == avi
    assert access.may_write(dana) is True
    c.post(f"/breakout/curators/teachers/{dana_profile.pk}/", {"action": "demote"})
    dana_profile.refresh_from_db()
    assert dana_profile.is_creator is False and dana_profile.creator_since is None and dana_profile.creator_by is None
    assert access.may_write(dana) is False and access.is_teacher(dana) is True
    # Only a teacher can be promoted; only a curator decides.
    assert c.post(f"/breakout/curators/teachers/{access.profile_for(asker).pk}/", {"action": "promote"}).status_code == 404
    assert _as(dana).post(f"/breakout/curators/teachers/{dana_profile.pk}/", {"action": "promote"}).status_code == 404
    dana_profile.refresh_from_db()
    assert dana_profile.is_creator is False
    # A curator is written down as one, with no promote or demote.
    curator = User.objects.create_user("lee", "lee@example.com", PASSWORD, first_name="לי")
    p = access.profile_for(curator)
    p.is_teacher, p.is_curator = True, True
    p.save()
    approved = _ul(c.get("/breakout/curators/teachers/").content.decode(), "br-approved")
    block = approved[approved.index("לי"):]
    assert 'br-tag--curator">אוצר/ת' in block and 'value="promote"' not in block and 'value="demote"' not in block


def test_the_api_tells_the_level_and_nobody_sets_it_from_there(seeded, dana):
    c = _as(dana)
    mine = c.get("/breakout/api/profiles/").json()
    rows = mine["results"] if isinstance(mine, dict) else mine
    assert len(rows) == 1 and rows[0]["is_teacher"] is True and rows[0]["is_creator"] is False
    r = c.patch(f"/breakout/api/profiles/{rows[0]['id']}/", {"is_creator": True, "is_teacher": True}, content_type="application/json")
    assert r.status_code == 200
    profile = Profile.objects.get(user=dana)
    assert profile.is_creator is False
    assert access.may_write(dana) is False
