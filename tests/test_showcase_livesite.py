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
    assert "thum.io" in p.screenshot_url
    assert ShowcaseProject(live_url="").screenshot_url == ""


def test_site_url_detects_hosted_repo_url():
    """A GitHub Pages / Vercel / Netlify repo_url IS the live site (REQ-6.3.16) —
    so it works even if the user put it in the 'code' field."""
    p = ShowcaseProject(live_url="", repo_url="https://avisalmon.github.io/shakshuka/")
    assert p.site_url == "https://avisalmon.github.io/shakshuka/"
    assert p.site_host == "avisalmon.github.io"
    # a plain GitHub repo is NOT a live site
    assert ShowcaseProject(repo_url="https://github.com/avi/shakshuka").site_url == ""
    # the live-demo field always wins
    p2 = ShowcaseProject(live_url="https://x.netlify.app/", repo_url="https://github.com/a/b")
    assert p2.site_url == "https://x.netlify.app/"


@pytest.mark.django_db
def test_card_links_to_live_site_and_shows_feedback():
    p = _project(live_url="https://avisalmon.github.io/shakshuka/", tagline="מתכונים")
    body = Client().get("/community/showcase/").content.decode()
    assert "avisalmon.github.io/shakshuka" in body   # cover (the image) → live site
    assert "thum.io" in body                          # auto screenshot cover
    assert "js-star" in body                         # inline star on the card
    # The image is the link now - no "אתר חי"/"בקרו" labels on the card.
    assert "בקרו" not in body
    assert "אתר חי" not in body


@pytest.mark.django_db
def test_detail_uses_screenshot_when_no_cover():
    p = _project(live_url="https://example.com/")
    body = Client().get(f"/community/showcase/p/{p.pk}/").content.decode()
    assert "thum.io" in body
    assert "example.com" in body          # the cover image links to the live site
    assert "בקרו באתר החי" not in body    # label removed; the image is the link
