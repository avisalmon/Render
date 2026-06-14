"""
EPIC-6.12 SPR-UX.1 — Tier-1 broken-path fixes: composer text-carry, global
flash messages, CrashTech self-service teams, @mention affordance + promote mark.
"""
import pytest
from django.contrib.auth.models import User
from django.test import Client
from django.utils import timezone


def _member(u="m", staff=False, guidelines=True):
    user = User.objects.create_user(u, password="p", is_staff=staff)
    user.profile.display_name = u
    if guidelines:
        user.profile.guidelines_accepted_at = timezone.now()
    user.profile.save()
    return user


def _client(user):
    c = Client(); c.force_login(user); return c


# --- F-6.12.1.1: composer text-carry ---

@pytest.mark.django_db
def test_composer_draft_prefills_forum_and_showcase():
    c = _client(_member("drafter"))
    body = c.get("/community/forum/new/?draft=" + "שאלה%20מהפיד").content.decode()
    assert "שאלה מהפיד" in body
    body2 = c.get("/community/showcase/new/?draft=" + "רעיון%20לפרויקט").content.decode()
    assert "רעיון לפרויקט" in body2


# --- F-6.12.1.3: global flash messages render once, everywhere ---

@pytest.mark.django_db
def test_flash_message_shows_once_after_redirect():
    c = _client(_member("flasher"))
    resp = c.post("/community/tips/new/", {"body": "טיפ לבדיקת הודעות"}, follow=True)
    body = resp.content.decode()
    assert body.count("הטיפ פורסם") == 1  # shown, exactly once (no double-render)


@pytest.mark.django_db
def test_base_has_single_messages_block():
    # base.html owns the only messages loop now
    with open("templates/base.html", encoding="utf-8") as f:
        assert "for message in messages" in f.read()
    with open("templates/app/community/tips_list.html", encoding="utf-8") as f:
        assert "for m in messages" not in f.read()  # local copy removed


# --- F-6.12.1.2: CrashTech self-service teams ---

def _hackathon(status="readiness", stock=2, team_size=2):
    from app.crashtech import grant_role
    from app.models import Hackathon
    org = _member("org", staff=True)
    h = Hackathon.objects.create(
        name="UX Cup", organizer=org, status=status,
        start_at=timezone.now() + timezone.timedelta(days=1),
        end_at=timezone.now() + timezone.timedelta(days=2),
        submission_deadline=timezone.now() + timezone.timedelta(days=2),
        team_size=team_size, hardware_stock=stock)
    grant_role(h, org, "organizer")
    return h


@pytest.mark.django_db
def test_participant_creates_own_team():
    from app.crashtech import grant_role
    from app.models import Team
    h = _hackathon()
    p = _member("racer")
    grant_role(h, p, "participant")
    resp = _client(p).post(f"/crashtech/{h.slug}/teams/create/", {"name": "Rockets"})
    assert resp.status_code == 302
    team = Team.objects.get(hackathon=h, name="Rockets")
    assert p in team.members.all()


@pytest.mark.django_db
def test_participant_joins_existing_team_until_full():
    from app.crashtech import grant_role
    from app.models import Team
    h = _hackathon(team_size=1, stock=3)
    team = Team.objects.create(hackathon=h, name="Comets", anon_ordinal=1)
    a, b = _member("a"), _member("b")
    grant_role(h, a, "participant"); grant_role(h, b, "participant")
    _client(a).post(f"/crashtech/{h.slug}/teams/{team.pk}/join/")
    assert a in team.members.all()
    # full now (team_size 1) → b blocked
    _client(b).post(f"/crashtech/{h.slug}/teams/{team.pk}/join/")
    assert b not in team.members.all()


@pytest.mark.django_db
def test_unteamed_participant_sees_guidance_not_deadend():
    from app.crashtech import grant_role
    from app.models import Challenge
    h = _hackathon(status="active")
    Challenge.objects.create(hackathon=h, title="Blink", point_value=100, visible=True)
    p = _member("lonely")
    grant_role(h, p, "participant")
    body = _client(p).get(f"/crashtech/{h.slug}/").content.decode()
    assert "צוות" in body  # explains they need a team, not a silent dead-end


# --- F-6.12.1.4: @mention affordance + promote mark ---

@pytest.mark.django_db
def test_channel_has_mention_datalist():
    from app.chat import ensure_topic_channels
    from app.models import Channel
    ensure_topic_channels()
    ch = Channel.objects.filter(kind="topic").first()
    _member("alice"); _member("bob")
    body = _client(_member("viewer")).get(f"/community/chat/{ch.slug}/").content.decode()
    assert "<datalist" in body and "alice" in body


@pytest.mark.django_db
def test_promoted_message_is_marked():
    from app.chat import ensure_topic_channels
    from app.models import Channel, ChannelMessage
    ensure_topic_channels()
    ch = Channel.objects.filter(kind="topic").first()
    author = _member("author")
    m = ChannelMessage.objects.create(channel=ch, author=author, body="פתרון שווה שיתוף")
    _client(author).post(f"/community/chat/message/{m.pk}/promote/", {"target": "forum"})
    m.refresh_from_db()
    assert m.promoted_to == "forum"
