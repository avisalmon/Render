"""SPR-7.8 / QA-16 — global breadcrumb trail + back button on every view."""
import pytest
from django.test import Client

from app.models import Course


@pytest.mark.django_db
def test_home_has_no_breadcrumb_bar():
    body = Client().get("/").content.decode()
    assert "bb-crumbbar" not in body


@pytest.mark.django_db
def test_section_page_shows_trail_and_back_button():
    body = Client().get("/community/").content.decode()
    assert "bb-crumbbar" in body          # the bar renders
    assert "bb-back" in body              # back button present
    assert "בית" in body and "קהילה" in body


@pytest.mark.django_db
def test_nested_page_shows_full_hierarchy_with_links():
    body = Client().get("/community/showcase/").content.decode()
    assert "דוכן השוויץ" in body
    # parent crumbs are clickable links back up the tree
    assert 'href="/community/"' in body
    assert 'href="/"' in body            # home crumb


@pytest.mark.django_db
def test_course_detail_breadcrumb_uses_real_title():
    Course.objects.create(slug="arduino", title="ארדואינו 2", is_published=True)
    body = Client().get("/courses/arduino/").content.decode()
    assert "bb-crumbbar" in body
    assert "ארדואינו 2" in body          # real course title, not a generic label
    assert "הדרכות" in body              # parent section link


def test_build_trail_for_named_url():
    from types import SimpleNamespace

    from app.breadcrumbs import build
    req = SimpleNamespace(resolver_match=SimpleNamespace(url_name="showcase_wall"))
    crumbs = build(req)
    labels = [c["label"] for c in crumbs]
    assert labels == ["בית", "קהילה", "דוכן השוויץ"]
    assert crumbs[0]["url_name"] == "home"      # home is a link
    assert crumbs[-1]["active"] is True          # current page is active/not linked
    assert crumbs[-1]["url_name"] is None


def test_chrome_free_pages_have_no_trail():
    from types import SimpleNamespace

    from app.breadcrumbs import build
    for name in ("home", "login", "register", "welcome"):
        req = SimpleNamespace(resolver_match=SimpleNamespace(url_name=name))
        assert build(req) == []
