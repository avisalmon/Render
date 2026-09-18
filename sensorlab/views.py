"""SensorLab's views.

The landing page is open — it is the front door, and it says what this is.
Everything past it needs an account (spec §9.1 A.2: the app is closed), and
the gate is SensorLab's own login page rather than the site's, which is why
`login_url` is passed explicitly instead of leaning on the project-wide
`LOGIN_URL` that belongs to babook.
"""

from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.utils.http import url_has_allowed_host_and_scheme

from .profiles import profile_for

sensorlab_login_required = login_required(login_url=reverse_lazy("sensorlab:login"))


def home(request):
    return render(request, "sensorlab/home.html")


@sensorlab_login_required
def design(request):
    """The design reference (SL-A4, spec §7): every component, both modes.

    Behind the gate rather than public — it is a working surface for whoever
    is building the app, not a page for a person doing an experiment. A board
    nobody can open is not a design system, so it lives in the app rather
    than in a static file somewhere.
    """
    return render(request, "sensorlab/design.html")


@sensorlab_login_required
def lab(request):
    """The first page behind the gate. A shell until Epic D's runner."""
    profile = profile_for(request.user)
    return render(request, "sensorlab/lab.html", {"profile": profile})


def set_language(request, code):
    """Switch the interface language (spec §1) and go back where you were.

    Works for a visitor who has not signed in yet — otherwise the sign-in
    page itself could not be read in Hebrew, and the switch would only be
    available to people who already got in. For someone signed in it also
    writes the profile, so the choice follows them to a new device rather
    than living in one browser's session.
    """
    from .middleware import SESSION_KEY
    from .profiles import profile_for
    from .strings import LANGUAGES

    if code not in LANGUAGES:
        raise Http404("no such language")

    request.session[SESSION_KEY] = code
    if request.user.is_authenticated:
        profile = profile_for(request.user)
        if profile.language != code:
            profile.language = code
            profile.save(update_fields=["language"])

    back = request.META.get("HTTP_REFERER", "")
    if not url_has_allowed_host_and_scheme(back, allowed_hosts={request.get_host()}):
        back = reverse_lazy("sensorlab:home")
    return redirect(back)
