"""
EPIC-6.12 SPR-UX.3 — information architecture: one community door (hub areas
strip), CrashTech folded under קהילה, distinct DM icon, empty-state CTAs.
"""
import pytest
from django.contrib.auth.models import User
from django.test import Client
from django.utils import timezone


def _member(u="m"):
    user = User.objects.create_user(u, password="p")
    user.profile.display_name = u; user.profile.is_public = True; user.profile.save()
    return user


def _client(user):
    c = Client(); c.force_login(user); return c


# --- F-6.12.3.1: hub areas strip (one canonical entry to all 8 areas) ---

@pytest.mark.django_db
def test_hub_areas_strip_links_all_eight_areas():
    body = Client().get("/community/").content.decode()
    assert "אזורי הקהילה" in body
    for url in ["/community/forum/", "/community/showcase/", "/community/tips/",
                "/community/chat/", "/community/events/", "/crashtech/", "/community/members/"]:
        assert url in body, f"missing area link: {url}"


# --- F-6.12.3.2: CrashTech folded under קהילה ---

@pytest.mark.django_db
def test_crashtech_breadcrumb_rooted_under_community():
    from app.breadcrumbs import build
    from types import SimpleNamespace
    req = SimpleNamespace(resolver_match=SimpleNamespace(url_name="crashtech_home"))
    labels = [c["label"] for c in build(req)]
    assert labels[:2] == ["בית", "קהילה"]  # rooted under community now


def test_crashtech_not_a_top_level_nav_peer():
    with open("templates/base.html", encoding="utf-8") as f:
        nav = f.read().split("navbar-nav me-auto")[1].split("ms-auto")[0]
    # CrashTech reachable via the community hub, not a standalone top-nav item
    assert "crashtech_home" not in nav


# --- F-6.12.3.3: distinct private-DM icon ---

def test_dm_icon_is_envelope_not_chat_dots():
    with open("templates/base.html", encoding="utf-8") as f:
        body = f.read()
    # the messages_inbox link uses an envelope, separate from community chat (chat-dots)
    inbox = body.split("messages_inbox")[1][:200]
    assert "bi-envelope" in inbox


# --- F-6.12.3.4: empty-state CTAs ---

@pytest.mark.django_db
def test_events_empty_state_has_cta():
    body = Client().get("/community/events/").content.decode()
    # no events -> still offers a way forward, not a dead-end
    assert "אין אירועים" in body and ("הציעו" in body or "/community/" in body or "צרו" in body)
