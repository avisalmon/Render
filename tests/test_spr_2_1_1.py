"""
SPR-2.1.1 - Corporate Page: Conversion MVP
TDD tests for F-2.1.1 through F-2.1.15.
Run: pytest -m spr211 -v
"""

import pytest
from django.apps import apps
from django.core import mail
from django.core.cache import cache
from django.test import Client, override_settings

pytestmark = [pytest.mark.spr211, pytest.mark.django_db]


def _content(response):
    return response.content.decode("utf-8", errors="ignore")


def _corporate_lead_model():
    return apps.get_model("app", "CorporateLead")


def test_corporate_page_renders_for_anonymous(client):
    """T-F-2.1.1-1: /corporate/ is anonymous-accessible and renders the MVP page."""
    response = client.get("/corporate/")
    html = _content(response)
    assert response.status_code == 200
    assert "corporate-page" in html
    assert "login" not in response.url if hasattr(response, "url") else True


def test_corporate_page_has_basic_seo_and_sitemap(client):
    """T-F-2.1.2-1: page has title/meta/canonical and appears in sitemap."""
    response = client.get("/corporate/")
    html = _content(response)
    assert "הדרכות AI לצוותי הנדסה" in html
    assert "AI training Israel" in html
    assert 'rel="canonical"' in html

    sitemap = _content(client.get("/sitemap.xml"))
    assert "/corporate/" in sitemap


def test_corporate_page_uses_fast_static_assets(client):
    """T-F-2.1.3-1: hero uses a static WebP asset and no framework bundle."""
    html = _content(client.get("/corporate/"))
    assert ".webp" in html
    # No SPA framework bundle (check the actual bundles, not bare substrings —
    # "react" legitimately appears in the showcase /react/ endpoint URL).
    assert "react-dom" not in html.lower()
    assert "vue.js" not in html.lower() and "vue@" not in html.lower()
    assert "angular.min" not in html.lower()


def test_corporate_page_responsive_structure(client):
    """T-F-2.1.4-1: page uses responsive Bootstrap layout and no fixed-width wrapper."""
    html = _content(client.get("/corporate/"))
    assert "col-12" in html
    assert "col-lg" in html
    assert "container" in html
    assert "width: 1200px" not in html


@override_settings(WHATSAPP_NUMBER="972501234567")
def test_hero_section_has_photo_copy_and_ctas(client):
    """T-F-2.1.5-1: hero has the expected headline, photo alt text, and CTAs."""
    html = _content(client.get("/corporate/"))
    assert "מאמן AI לצוותי הנדסה" in html
    assert "אבי סלמון" in html
    assert "דבר איתי בוואטסאפ" in html
    assert "#corporate-lead-form" in html
    assert "wa.me/972501234567" in html


def test_static_service_tier_cards(client):
    """T-F-2.1.6-1: workshop, bootcamp, and keynote tier cards render from page-local data."""
    html = _content(client.get("/corporate/"))
    for text in ["סדנה", "בוטקאמפ", "הרצאה", "₪15,000", "₪35,000", "₪9,000", "מע״מ"]:
        assert text in html
    assert "הכי פופולרי" in html
    assert html.count("corporate-tier-card") >= 3


def test_faq_accordion_content(client):
    """T-F-2.1.7-1: static Hebrew FAQ renders as a Bootstrap accordion."""
    html = _content(client.get("/corporate/"))
    assert "accordion" in html
    assert html.count("accordion-item") >= 6
    assert "מה ההבדל בין סדנה לבוטקאמפ" in html
    assert "האם אפשר להתאים את התוכן לצוות שלנו" in html


def test_contact_form_ui_fields_and_accessibility(client):
    """T-F-2.1.8-1: form exposes required fields, labels, and aria-live status."""
    html = _content(client.get("/corporate/"))
    for field in ["name", "company", "role", "team_size", "training_type", "message"]:
        assert f'name="{field}"' in html
        assert f'for="id_{field}"' in html
    assert "aria-live" in html
    assert "corporate-form-status" in html


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
def test_contact_form_submit_creates_lead_and_sends_email(client):
    """T-F-2.1.9-1: AJAX submit creates CorporateLead and emails Avi."""
    cache.clear()
    CorporateLead = _corporate_lead_model()
    response = client.post(
        "/corporate/",
        {
            "name": "Dana Levi",
            "company": "Acme AI",
            "role": "VP R&D",
            "team_size": "16-50",
            "training_type": "bootcamp",
            "message": "Need practical AI training",
            "utm_source": "linkedin",
        },
        HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        HTTP_REFERER="https://example.com/post",
        REMOTE_ADDR="203.0.113.10",
    )
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    lead = CorporateLead.objects.get(company="Acme AI")
    assert lead.training_type == "bootcamp"
    assert lead.utm_source == "linkedin"
    assert lead.referrer_url == "https://example.com/post"
    assert lead.ip_hash and "203.0.113.10" not in lead.ip_hash
    assert len(mail.outbox) == 1
    assert "Acme AI" in mail.outbox[0].subject


def test_honeypot_silently_rejects_without_db_write(client):
    """T-F-2.1.10-1: filled honeypot returns 200 but creates no lead."""
    cache.clear()
    CorporateLead = _corporate_lead_model()
    response = client.post(
        "/corporate/",
        {
            "name": "Bot",
            "company": "Spam Ltd",
            "team_size": "1-5",
            "training_type": "workshop",
            "website": "https://spam.example",
        },
        HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        REMOTE_ADDR="203.0.113.11",
    )
    assert response.status_code == 200
    assert CorporateLead.objects.count() == 0


def test_rate_limit_blocks_fourth_submission(client):
    """T-F-2.1.10-2: max 3 submissions per IP per hour."""
    cache.clear()
    for index in range(3):
        response = client.post(
            "/corporate/",
            {
                "name": f"Lead {index}",
                "company": f"Company {index}",
                "team_size": "1-5",
                "training_type": "workshop",
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
            REMOTE_ADDR="203.0.113.12",
        )
        assert response.status_code == 200

    blocked = client.post(
        "/corporate/",
        {
            "name": "Lead 4",
            "company": "Company 4",
            "team_size": "1-5",
            "training_type": "workshop",
        },
        HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        REMOTE_ADDR="203.0.113.12",
    )
    assert blocked.status_code == 429


@override_settings(WHATSAPP_NUMBER="972501234567")
def test_whatsapp_links_use_env_number_and_encoded_messages(client):
    """T-F-2.1.11-1: hero, tier, footer, and sticky WhatsApp links are prefilled."""
    html = _content(client.get("/corporate/"))
    assert html.count("wa.me/972501234567") >= 5
    assert "text=" in html
    assert "%D7" in html
    assert "bi-whatsapp" in html


def test_utm_capture_and_plausible_form_event(client):
    """T-F-2.1.12-1: hidden UTM fields and corporate_form_submit event are present."""
    html = _content(client.get("/corporate/?utm_source=linkedin&utm_campaign=launch"))
    for field in ["utm_source", "utm_medium", "utm_campaign", "utm_content"]:
        assert f'name="{field}"' in html
    assert "corporate_form_submit" in html
    assert "URLSearchParams" in html


def test_accessibility_baseline_markup(client):
    """T-F-2.1.13-1: semantic structure, skip link, labels, and reduced motion exist."""
    html = _content(client.get("/corporate/"))
    assert html.count("<h1") == 1
    assert "skip-to-content" in html
    assert "aria-label" in html
    assert "prefers-reduced-motion" in html


def test_mobile_specific_classes(client):
    """T-F-2.1.14-1: mobile hero, stacked cards, and sticky-safe form styling are present."""
    html = _content(client.get("/corporate/"))
    assert "corporate-hero-photo" in html
    assert "corporate-form-section" in html
    assert "col-12 col-lg-4" in html
    assert "min-height: 48px" in html or "min-height:48px" in html


def test_csrf_enforced_for_ajax_submit():
    """T-F-2.1.15-1: AJAX submit rejects missing CSRF when checks are enforced."""
    client = Client(enforce_csrf_checks=True)
    response = client.post(
        "/corporate/",
        {
            "name": "No CSRF",
            "company": "Acme",
            "team_size": "1-5",
            "training_type": "workshop",
        },
        HTTP_X_REQUESTED_WITH="XMLHttpRequest",
    )
    assert response.status_code == 403


def test_input_sanitization_strips_html_and_limits_message(client):
    """T-F-2.1.15-2: message strips HTML tags and is limited to 1000 chars."""
    cache.clear()
    CorporateLead = _corporate_lead_model()
    response = client.post(
        "/corporate/",
        {
            "name": "Clean Me",
            "company": "Safe Co",
            "team_size": "6-15",
            "training_type": "not_sure",
            "message": "<script>alert(1)</script>" + ("x" * 1200),
        },
        HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        REMOTE_ADDR="203.0.113.13",
    )
    assert response.status_code == 200
    lead = CorporateLead.objects.get(company="Safe Co")
    assert "<script>" not in lead.message
    assert len(lead.message) <= 1000
