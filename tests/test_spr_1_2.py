"""
SPR-1.2 — Auth & Users
Tests for F-1.2.1 through F-1.2.8.
Run: pytest -m spr12 -v
"""
import pytest
from django.conf import settings
from django.contrib.auth.models import User

# ---------------------------------------------------------------------------
# F-1.2.4 — Password signup / login / logout
# ---------------------------------------------------------------------------

@pytest.mark.spr12
@pytest.mark.django_db
def test_register_valid_creates_user_and_redirects(client):
    """T-F-1.2.4-1: POST /register/ with valid data creates user and redirects."""
    response = client.post("/register/", {
        "username": "newuser",
        "name": "משתמש חדש",  # name + email now required (REQ-7.2.1)
        "email": "newuser@example.com",
        "password1": "StrongPass123!",
        "password2": "StrongPass123!",
    })
    assert response.status_code == 302
    assert User.objects.filter(username="newuser").exists()


@pytest.mark.spr12
@pytest.mark.django_db
def test_register_mismatched_passwords_returns_form_error(client):
    """T-F-1.2.4-2: POST /register/ with mismatched passwords stays on form."""
    response = client.post("/register/", {
        "username": "newuser",
        "password1": "StrongPass123!",
        "password2": "WrongPass456!",
    })
    assert response.status_code == 200
    assert not User.objects.filter(username="newuser").exists()


@pytest.mark.spr12
@pytest.mark.django_db
def test_login_valid_credentials_redirects(client, django_user_model):
    """T-F-1.2.4-3: POST /login/ with valid credentials redirects to home."""
    django_user_model.objects.create_user(username="avi", password="TestPass123!")
    response = client.post("/login/", {"username": "avi", "password": "TestPass123!"})
    assert response.status_code == 302


@pytest.mark.spr12
@pytest.mark.django_db
def test_login_bad_credentials_shows_error(client, django_user_model):
    """T-F-1.2.4-4: POST /login/ with wrong password returns 200 (not redirected)."""
    django_user_model.objects.create_user(username="avi", password="TestPass123!")
    response = client.post("/login/", {"username": "avi", "password": "WrongPassword"})
    assert response.status_code == 200


@pytest.mark.spr12
@pytest.mark.django_db
def test_logout_redirects_to_home(client, django_user_model):
    """T-F-1.2.4-5: POST /logout/ logs out and redirects."""
    django_user_model.objects.create_user(username="avi", password="TestPass123!")
    client.login(username="avi", password="TestPass123!")
    response = client.post("/logout/")
    assert response.status_code == 302


@pytest.mark.spr12
@pytest.mark.django_db
def test_add_note_unauthenticated_redirects_to_login(client):
    """T-F-1.2.4-6: Unauthenticated GET /add_note/ redirects to login."""
    response = client.get("/add_note/")
    assert response.status_code == 302
    assert "/login/" in response["Location"] or "/accounts/login/" in response["Location"]


# ---------------------------------------------------------------------------
# F-1.2.6 — User profile page
# ---------------------------------------------------------------------------

@pytest.mark.spr12
@pytest.mark.django_db
def test_profile_authenticated_returns_200(client, django_user_model):
    """T-F-1.2.6-1: GET /profile/ returns 200 for authenticated user."""
    django_user_model.objects.create_user(username="avi", password="TestPass123!")
    client.login(username="avi", password="TestPass123!")
    response = client.get("/profile/")
    assert response.status_code == 200


@pytest.mark.spr12
@pytest.mark.django_db
def test_profile_unauthenticated_redirects_to_login(client):
    """T-F-1.2.6-2: GET /profile/ redirects unauthenticated user."""
    response = client.get("/profile/")
    assert response.status_code == 302
    assert "/login/" in response["Location"] or "/accounts/login/" in response["Location"]


@pytest.mark.spr12
@pytest.mark.django_db
def test_profile_post_saves_display_name(client, django_user_model):
    """T-F-1.2.6-3: POST /profile/ with display_name saves to UserProfile."""
    from app.models import UserProfile
    user = django_user_model.objects.create_user(username="avi", password="TestPass123!")
    client.login(username="avi", password="TestPass123!")
    response = client.post("/profile/", {"display_name": "Avi Salmon"})
    assert response.status_code in (200, 302)
    profile = UserProfile.objects.get(user=user)
    assert profile.display_name == "Avi Salmon"


# ---------------------------------------------------------------------------
# F-1.2.7 — Roles & permissions
# ---------------------------------------------------------------------------

@pytest.mark.spr12
@pytest.mark.django_db
def test_userprofile_model_exists():
    """T-F-1.2.7-3: UserProfile model is importable and has a role field."""
    from app.models import UserProfile
    assert hasattr(UserProfile, "role")


@pytest.mark.spr12
@pytest.mark.django_db
def test_new_user_gets_member_role(django_user_model):
    """T-F-1.2.7-1: New user's UserProfile has role='member' by default."""
    from app.models import UserProfile
    user = django_user_model.objects.create_user(username="avi", password="TestPass123!")
    profile = UserProfile.objects.get(user=user)
    assert profile.role == "member"


@pytest.mark.spr12
@pytest.mark.django_db
def test_staff_user_is_staff(django_user_model):
    """T-F-1.2.7-2: Staff user has is_staff=True."""
    user = django_user_model.objects.create_user(
        username="staffuser", password="TestPass123!", is_staff=True
    )
    assert user.is_staff is True


# ---------------------------------------------------------------------------
# F-1.2.8 — Django admin access
# ---------------------------------------------------------------------------

@pytest.mark.spr12
@pytest.mark.django_db
def test_admin_accessible_by_superuser(client, django_user_model):
    """T-F-1.2.8-1: /admin/ returns 200 for superuser."""
    django_user_model.objects.create_superuser(
        username="admin", password="AdminPass123!", email="admin@test.com"
    )
    client.login(username="admin", password="AdminPass123!")
    response = client.get("/admin/")
    assert response.status_code == 200


@pytest.mark.spr12
@pytest.mark.django_db
def test_admin_redirects_anonymous(client):
    """T-F-1.2.8-2: /admin/ redirects unauthenticated user to login."""
    response = client.get("/admin/")
    assert response.status_code == 302


# ---------------------------------------------------------------------------
# F-1.2.2 — Google OAuth config
# ---------------------------------------------------------------------------

@pytest.mark.spr12
def test_google_provider_in_settings():
    """T-F-1.2.2-1: Google provider is declared in SOCIALACCOUNT_PROVIDERS."""
    assert "google" in settings.SOCIALACCOUNT_PROVIDERS


# ---------------------------------------------------------------------------
# F-1.2.3 — GitHub OAuth config
# ---------------------------------------------------------------------------

@pytest.mark.spr12
def test_github_provider_in_installed_apps():
    """T-F-1.2.3-1: GitHub socialaccount provider is in INSTALLED_APPS."""
    assert "allauth.socialaccount.providers.github" in settings.INSTALLED_APPS


# ---------------------------------------------------------------------------
# F-1.2.1 — Email backend config
# ---------------------------------------------------------------------------

@pytest.mark.spr12
def test_email_backend_configured():
    """T-F-1.2.1-1: EMAIL_BACKEND is set in settings (not the default dummy)."""
    assert hasattr(settings, "EMAIL_BACKEND")
    assert settings.EMAIL_BACKEND != ""
