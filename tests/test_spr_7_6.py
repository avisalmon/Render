"""
SPR-7.6 — Contact email reliability (REQ-7.6.1 / QA-19).
"""
import pytest
from django.core import mail
from django.test import Client, override_settings

from app.models import CorporateLead


@override_settings(CONTACT_NOTIFY_EMAIL="avi@example.com")
@pytest.mark.django_db
def test_contact_lead_stored_and_emailed_to_admin():
    resp = Client().post("/corporate/", {
        "name": "דנה", "company": "אקמה", "email": "dana@acme.com",
        "training_type": "workshop", "team_size": "10", "message": "מעוניינים בהדרכה",
    }, HTTP_X_REQUESTED_WITH="XMLHttpRequest")
    assert resp.status_code == 200
    assert CorporateLead.objects.filter(company="אקמה").exists()  # admin-visible
    assert len(mail.outbox) == 1
    assert "avi@example.com" in mail.outbox[0].to  # reaches Avi's inbox


@pytest.mark.django_db
def test_privacy_terms_offer_contact_form():
    pbody = Client().get("/privacy/").content.decode()
    tbody = Client().get("/terms/").content.decode()
    assert "טופס יצירת הקשר" in pbody
    assert "טופס יצירת הקשר" in tbody
