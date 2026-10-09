"""The front door: log in, sign up and log out, inside improv's own pages (spec ch. 7).

A person given the link is not sent to babook. They get these pages, in English, in the app's own
look. The account is still the site's ordinary account (one email and password works on babook and
here), made with the ordinary User; improv adds nothing to it. Google sign in goes through the site's
sign in and comes straight back.
"""

import hashlib

from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.shortcuts import redirect, render
from django.utils.text import slugify
from django.views.decorators.http import require_POST

from .access import HOME, LOGIN, SIGNUP, client_ip, safe_next

GOOGLE_URL = "/accounts/google/login/?process=login&next=/improv/"
BACKEND = "django.contrib.auth.backends.ModelBackend"

LOGIN_TRIES = 10
LOGIN_LOCK_SECONDS = 15 * 60
SIGNUPS_PER_IP_HOUR = 10
NAME_MAX = 30
EMAIL_MAX = 254


def _digest(*parts):
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:32]


def _context(request, **extra):
    context = {
        "next": safe_next(request.POST.get("next") or request.GET.get("next") or ""),
        "google_url": GOOGLE_URL,
        "login_url": LOGIN,
        "signup_url": SIGNUP,
    }
    context.update(extra)
    return context


def front_door(request, **extra):
    """The page a visitor sees at /improv/: what the app is, and one way in."""
    return render(request, "improv/welcome.html", _context(request, **extra))


def login_page(request, **extra):
    return render(request, "improv/login.html", _context(request, **extra))


def login_view(request):
    if request.user.is_authenticated:
        return redirect(HOME)
    if request.method != "POST":
        return login_page(request)

    ident = request.POST.get("email", "").strip()[:EMAIL_MAX]
    password = request.POST.get("password", "")
    lock = f"improv_login_{_digest(client_ip(request), ident.lower())}"
    if cache.get(lock, 0) >= LOGIN_TRIES:
        return login_page(request, error="Too many tries. Wait a few minutes and try again.", email=ident)
    if not ident or not password:
        return login_page(request, error="Enter your email and your password.", email=ident)
    user = authenticate(request, username=ident, password=password)
    if user is None:
        cache.set(lock, cache.get(lock, 0) + 1, LOGIN_LOCK_SECONDS)
        return login_page(request, error="That email and password did not match.", email=ident)
    cache.delete(lock)
    login(request, user)
    return redirect(safe_next(request.POST.get("next")))


def _username_for(email):
    base = (slugify(email.split("@")[0]) or "player")[:140]
    name, n = base, 1
    while User.objects.filter(username__iexact=name).exists():
        n += 1
        name = f"{base}{n}"
    return name


def _problems(email, password, name):
    try:
        validate_email(email)
    except ValidationError:
        return "Enter an email address that works, like you@example.com."
    if len(email) > EMAIL_MAX:
        return "That email address is too long."
    if User.objects.filter(email__iexact=email).exists():
        return "That email already has an account. Log in instead."
    try:
        validate_password(password, user=User(email=email, first_name=name))
    except ValidationError as error:
        return " ".join(error.messages)
    return ""


def signup_view(request):
    if request.user.is_authenticated:
        return redirect(HOME)
    if request.method != "POST":
        return render(request, "improv/signup.html", _context(request))

    email = request.POST.get("email", "").strip().lower()
    name = request.POST.get("name", "").strip()[:NAME_MAX]
    password = request.POST.get("password", "")
    typed = {"email": email, "name": name}

    cap = f"improv_signups_{_digest(client_ip(request))}"
    if cache.get(cap, 0) >= SIGNUPS_PER_IP_HOUR:
        return render(request, "improv/signup.html", _context(request, error="Too many accounts were made from here in the last hour. Try again later.", **typed))
    problem = _problems(email, password, name)
    if problem:
        return render(request, "improv/signup.html", _context(request, error=problem, **typed))

    user = User.objects.create_user(username=_username_for(email), email=email, password=password)
    if name:
        user.first_name = name
        user.save(update_fields=["first_name"])
    cache.set(cap, cache.get(cap, 0) + 1, 3600)
    login(request, user, backend=BACKEND)
    return redirect(safe_next(request.POST.get("next")))


@require_POST
def logout_view(request):
    logout(request)
    return redirect(HOME)
