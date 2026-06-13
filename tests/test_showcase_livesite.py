"""
REQ-6.3.16 — live-site project cards: auto screenshot/favicon cover, cover →
live site, inline star + counts on the card.
"""
import pytest
from django.contrib.auth.models import User
from django.test import Client
from django.utils import timezone

from app.models import ShowcaseProject


def _project(**kw):
    u = User.objects.create_user(kw.pop("u", "builder"), password="p")
    u.profile.display_name = "בונה"
    u.profile.save()
    kw.setdefault("title", "אתר השקשוקה")
    kw.setdefault("status", "published")
    kw.setdefault("published_at", timezone.now())
    return ShowcaseProject.objects.create(author=u, **kw)


def test_model_site_helpers():
    p = ShowcaseProject(live_url="https://avisalmon.github.io/shakshuka/")
    assert p.site_host == "avisalmon.github.io"
    assert "favicons" in p.favicon_url and "avisalmon.github.io" in p.favicon_url
    assert "mshots" in p.screenshot_url
    assert ShowcaseProject(live_url="").screenshot_url == ""


@pytest.mark.django_db
def test_card_links_to_live_site_and_shows_feedback():
    p = _project(live_url="https://avisalmon.github.io/shakshuka/", tagline="מתכונים")
    body = Client().get("/community/showcase/").content.decode()
    assert "avisalmon.github.io/shakshuka" in body   # cover/visit → live site
    assert "mshots" in body                          # auto screenshot cover
    assert "js-star" in body                         # inline star on the card
    assert "בקרו" in body                            # visit CTA


@pytest.mark.django_db
def test_detail_uses_screenshot_when_no_cover():
    p = _project(live_url="https://example.com/")
    body = Client().get(f"/community/showcase/p/{p.pk}/").content.decode()
    assert "mshots" in body
    assert "בקרו באתר החי" in body
