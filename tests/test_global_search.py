"""Site-wide search in the main menu: courses, people, projects, community."""
import pytest
from django.contrib.auth.models import User
from django.test import Client

from app.models import Course, ShowcaseProject

pytestmark = pytest.mark.django_db


def test_search_finds_courses_people_and_projects():
    Course.objects.create(title="Python Wizardry", slug="pyw", is_published=True)
    z = User.objects.create_user("zelda", password="p")
    z.profile.is_public = True; z.profile.display_name = "Zelda Hacker"; z.profile.save()
    author = User.objects.create_user("maker9", password="p")
    ShowcaseProject.objects.create(author=author, title="Python Robot", status="published")

    groups = {g["label"]: g for g in Client().get("/search/json/?q=python").json()["groups"]}
    assert "הדרכות" in groups
    assert any(it["title"] == "Python Wizardry" for it in groups["הדרכות"]["items"])
    assert "פרויקטים" in groups

    people = {g["label"] for g in Client().get("/search/json/?q=zelda").json()["groups"]}
    assert "אנשים" in people


def test_search_excludes_private_people():
    s = User.objects.create_user("secretive", password="p")
    s.profile.is_public = False; s.profile.display_name = "Secretive One"; s.profile.save()
    groups = Client().get("/search/json/?q=secretive").json()["groups"]
    assert all(g["label"] != "אנשים" for g in groups)


def test_search_page_and_empty_query():
    assert Client().get("/search/").status_code == 200
    assert Client().get("/search/json/?q=").json()["groups"] == []


def test_search_link_in_nav():
    assert "/search/" in Client().get("/").content.decode()
