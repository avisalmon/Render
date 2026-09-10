"""מט״צים views.

Design-first still holds for anything the program has not decided yet: the
stats and showcase from Litala's prototype stay off the page until real data
and real consent exist (REQ-M.5e, REQ-M.5f), and מבחן הכניסה is a page that
explains itself rather than a test that pretends to grade.

Identity, though, is real from here on. Login and registration write to the
shared `User`, the profile reads babook's `UserProfile` and the course engine
live, and only מט״צים's own flags are ours (matazim/models.py).
"""

from django.contrib.auth import authenticate
from django.contrib.auth import login as auth_login
from django.contrib.auth import logout as auth_logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db import transaction
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from app.models import CourseCertificate, Enrollment, UserProfile

from .content import public_stages
from .models import MemberProfile

# Anonymous visitors have no row to write to, so their acknowledgement of the
# prototype notice lives in the session. It cannot be attributed to anyone,
# which is exactly why REQ-M.40 stores it on the profile for people who signed
# in. What it must not do is nag them on every page.
WELCOME_SESSION_KEY = "mz_welcome_accepted"

# --- Shared helpers ---------------------------------------------------------


def member_profile(user):
    """The מט״צים row for a signed-in person, created the first time we need it."""
    if not user.is_authenticated:
        return None
    profile, _ = MemberProfile.objects.get_or_create(user=user)
    return profile


def welcome_is_pending(request):
    """REQ-M.39 — has this person been told the site is a prototype?"""
    if request.user.is_authenticated:
        return not member_profile(request.user).has_accepted_welcome()
    return not request.session.get(WELCOME_SESSION_KEY, False)


def student_door_is_open(request):
    """REQ-M.36 — כניסת תלמידים waits for the entrance test.

    Anonymous means not yet, because there is nowhere to have recorded a pass.
    כניסת מובילים deliberately does not consult this: the test measures a
    teenager's commitment, and a teacher confirming a roster has no reason to
    model a 3D object.
    """
    if not request.user.is_authenticated:
        return False
    return member_profile(request.user).has_passed_entrance_test()


def shell(request, section, **extra):
    """Context every מט״צים page needs, so base.html never guesses."""
    ctx = {
        "section": section,
        "welcome_pending": welcome_is_pending(request),
        "member": member_profile(request.user),
    }
    ctx.update(extra)
    return ctx


# --- Public front -----------------------------------------------------------


def home(request):
    """REQ-M.5 — דף הבית, open to anyone."""
    return render(
        request,
        "matazim/home.html",
        shell(
            request,
            "home",
            stages=public_stages(),
            student_door_open=student_door_is_open(request),
        ),
    )


def entrance_test(request):
    """REQ-M.38 — מבחן הכניסה has a home before it has a test.

    Public on purpose (REQ-M.5d): the link gets pasted around, and signing up
    happens around the test rather than before it. The Tinkercad task itself is
    REQ-M.17 and lands in its own sprint.
    """
    return render(request, "matazim/entrance_test.html", shell(request, "test"))


# --- The threshold ----------------------------------------------------------


def login(request):
    """REQ-M.6, REQ-M.7 — our screen, babook's accounts, no linking step."""
    if request.user.is_authenticated:
        return redirect("matazim:home")

    error = ""
    email = ""
    if request.method == "POST":
        email = (request.POST.get("email") or "").strip().lower()
        password = request.POST.get("password") or ""
        # Accounts are keyed by email here (ACCOUNT_LOGIN_METHODS), but the
        # username is what ModelBackend authenticates against, so resolve one
        # to the other rather than assuming they match.
        match = User.objects.filter(email__iexact=email).first()
        user = authenticate(request, username=match.username if match else email, password=password)
        if user is None:
            error = "האימייל או הסיסמה שגויים. נסו שוב."
        else:
            auth_login(request, user, backend="django.contrib.auth.backends.ModelBackend")
            _stamp_entry(user)
            _carry_welcome_across_sign_in(request, user)
            return redirect(request.POST.get("next") or "matazim:home")

    return render(
        request,
        "matazim/login.html",
        shell(request, "login", error=error, email=email),
    )


@require_POST
def logout(request):
    auth_logout(request)
    return redirect("matazim:home")


def register(request):
    """REQ-M.6 — three fields, because every extra one is a teenager who stops."""
    if request.user.is_authenticated:
        return redirect("matazim:home")

    error = ""
    name = ""
    email = ""
    if request.method == "POST":
        name = (request.POST.get("name") or "").strip()
        email = (request.POST.get("email") or "").strip().lower()
        password = request.POST.get("password") or ""

        if not name or not email or len(password) < 8:
            error = "צריך שם, אימייל וסיסמה באורך 8 תווים לפחות."
        elif User.objects.filter(email__iexact=email).exists():
            # Deliberately not "this account already exists": that tells a
            # stranger who is registered here, and these are minors.
            error = "לא הצלחנו לפתוח חשבון עם האימייל הזה. נסו להתחבר במקום."
        else:
            with transaction.atomic():
                user = User.objects.create_user(username=email, email=email, password=password)
                UserProfile.objects.update_or_create(user=user, defaults={"display_name": name})
                MemberProfile.objects.update_or_create(
                    user=user, defaults={"entered_via_matazim": True}
                )
            auth_login(request, user, backend="django.contrib.auth.backends.ModelBackend")
            _carry_welcome_across_sign_in(request, user)
            # REQ-M.46 - the main view, not the personal area. Someone who has
            # just signed in wants to see the program, not a form about
            # themselves, and the personal area is one click away in the header.
            return redirect("matazim:home")

    return render(
        request,
        "matazim/register.html",
        shell(request, "register", error=error, name=name, email=email),
    )


def google_start(request):
    """REQ-M.45 — hand off to Google without the page ever linking out.

    A direct link to the provider would be an href outside /matazim/ and would
    break RULE-1. Linking to our own URL instead keeps the seal intact, and the
    return address we name brings them back inside the prefix, so they go from
    our screen to Google's and back to ours without touching a babook page.
    """
    target = reverse("matazim:auth_done")
    return redirect(f"{reverse('google_login')}?process=login&next={target}")


def auth_done(request):
    """Where the provider drops them. The same bookkeeping as a password login.

    How someone got in should not change what we record about them, so entry is
    stamped and a welcome accepted as a stranger is carried over here too.
    Someone who abandoned the consent screen arrives unauthenticated; that is a
    change of mind, not an error, so they get the login page back.
    """
    if not request.user.is_authenticated:
        return redirect("matazim:login")
    _stamp_entry(request.user)
    _carry_welcome_across_sign_in(request, request.user)
    return redirect("matazim:home")


def _carry_welcome_across_sign_in(request, user):
    """Someone who accepted the notice as a stranger has still accepted it.

    Without this, dismissing the welcome and then registering shows it a second
    time, and the acceptance we do have on record is thrown away. Promoting the
    session flag onto the profile fixes both: they are asked once, and REQ-M.40
    gets the timestamp it is supposed to keep.
    """
    if not request.session.get(WELCOME_SESSION_KEY):
        return
    profile, _ = MemberProfile.objects.get_or_create(user=user)
    if profile.welcome_accepted_at is None:
        profile.welcome_accepted_at = timezone.now()
        profile.save(update_fields=["welcome_accepted_at", "updated_at"])


def _stamp_entry(user):
    """REQ-M.35 — signing in through this app's own button marks the door used."""
    profile, created = MemberProfile.objects.get_or_create(
        user=user, defaults={"entered_via_matazim": True}
    )
    if not created and not profile.entered_via_matazim:
        profile.entered_via_matazim = True
        profile.save(update_fields=["entered_via_matazim", "updated_at"])


# --- First contact ----------------------------------------------------------


@require_POST
def welcome_accept(request):
    """REQ-M.40 — an explicit acknowledgement, kept where it can be shown."""
    if request.user.is_authenticated:
        MemberProfile.objects.update_or_create(
            user=request.user, defaults={"welcome_accepted_at": timezone.now()}
        )
    request.session[WELCOME_SESSION_KEY] = True
    return redirect(request.POST.get("next") or "matazim:home")


@require_POST
@login_required(login_url="/matazim/login/")
def profile_reset_welcome(request):
    """REQ-M.41 — meet the site as a stranger again, as often as you like."""
    MemberProfile.objects.update_or_create(
        user=request.user, defaults={"welcome_accepted_at": None}
    )
    request.session[WELCOME_SESSION_KEY] = False
    return redirect("matazim:home")


# --- The profile ------------------------------------------------------------


def training_record(user):
    """REQ-M.44 — read live from the course engine, never copied (RULE-3).

    Everything the person has done anywhere on babook counts, including work
    done long before מט״צים existed. That is the retroactive-credit rule
    falling out of the design rather than needing a backfill.
    """
    enrollments = (
        Enrollment.objects.filter(user=user).select_related("course").order_by("-enrolled_at")
    )
    certified = set(CourseCertificate.objects.filter(user=user).values_list("course_id", flat=True))
    done, doing = [], []
    for enrollment in enrollments:
        row = {
            "course": enrollment.course,
            "certified": enrollment.course_id in certified,
            "completed_at": enrollment.completed_at,
        }
        (done if enrollment.completed_at else doing).append(row)
    return {"done": done, "doing": doing, "total": len(done) + len(doing)}


@login_required(login_url="/matazim/login/")
def profile(request):
    """REQ-M.42 to M.44 — one identity, shown the way מט״צים needs it."""
    user_profile, _ = UserProfile.objects.get_or_create(user=request.user)

    saved = False
    if request.method == "POST":
        # The name is the shared one on purpose. Editing it here changes it on
        # babook too, because a person has one name (REQ-M.42).
        display_name = (request.POST.get("display_name") or "").strip()
        if display_name:
            user_profile.display_name = display_name
            user_profile.save(update_fields=["display_name"])
            saved = True

    return render(
        request,
        "matazim/profile.html",
        shell(
            request,
            "profile",
            user_profile=user_profile,
            training=training_record(request.user),
            saved=saved,
        ),
    )


# --- The rest of the front ---------------------------------------------------
#
# Litala's nine sections. SPR-M.1 built דף הבית and left the other eight
# pointing back at it, which reads as broken rather than unfinished: a menu item
# that silently reloads the page you are on is worse than one that is missing.
#
# The rule here is the one the stats band and the showcase established. Where
# the data exists we show it. Where it does not we say what is coming, in our
# own voice, and we invent nothing.


def about(request):
    """REQ-M.57 — what this is, who it is for, who runs it."""
    from .content import FUNNEL

    return render(request, "matazim/about.html", shell(request, "about", funnel=FUNNEL))


def track(request):
    """REQ-M.58 — the five stages as a path.

    All five here, including מתמיינים. The home page teaser sells the journey
    and leaves the selection stage out because the entrance test has its own
    call to action there; this page is the journey itself.
    """
    from .content import FUNNEL

    return render(request, "matazim/track.html", shell(request, "track", funnel=FUNNEL))


def courses(request):
    """REQ-M.59 — the training path, honest about what is open today.

    Listing a track nobody can start yet would be the stats-band mistake again.
    What is real today is the entrance test, so that is what the page offers.
    """
    return render(request, "matazim/courses.html", shell(request, "courses"))


def _coming(request, key, section):
    from .content import COMING

    return render(
        request,
        "matazim/coming.html",
        shell(request, section, page=COMING[key]),
    )


def schools(request):
    """REQ-M.60 — no `School` model yet, so the page says so."""
    return _coming(request, "schools", "schools")


def community(request):
    """REQ-M.60 — no `Post` model yet."""
    return _coming(request, "community", "community")


def events(request):
    """REQ-M.60 — no `Event` model yet."""
    return _coming(request, "events", "events")
