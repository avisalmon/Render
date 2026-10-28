"""The OpenSCAD check page (app/openscad_check.py): a superuser only, and it
answers even where OpenSCAD is not installed (this PC, a failed download)."""

import pytest
from django.contrib.auth.models import User


@pytest.mark.django_db
def test_only_a_superuser_reaches_the_check(client):
    assert client.get("/internal/openscad-check/").status_code == 404
    dana = User.objects.create_user("d@example.com", "d@example.com", "pass-12345-x", is_staff=True)
    client.force_login(dana)
    assert client.get("/internal/openscad-check/").status_code == 404


@pytest.mark.django_db
def test_without_the_binary_it_says_so(client, monkeypatch, tmp_path):
    from app import openscad_check

    monkeypatch.setattr(openscad_check, "BIN", tmp_path / "missing" / "AppRun")
    avi = User.objects.create_superuser("a@example.com", "a@example.com", "pass-12345-x")
    client.force_login(avi)
    r = client.get("/internal/openscad-check/")
    assert r.status_code == 200 and r.json()["installed"] is False


def test_the_fixture_is_the_test_box():
    from app import openscad_check

    text = openscad_check.FIXTURE.read_text(encoding="utf-8")
    assert "100" in text and "80" in text and "27" in text
