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


def sensor_check(request):
    """Epic C's spike, reachable without an account (spec §9.3).

    The whole app rests on one assumption: that a page served over the web
    can read this phone's sensors. That is checkable on a real device in
    about ten seconds, and no amount of reading documentation substitutes
    for doing it — so this page reports what the browser in your hand
    actually does, including when the answer is "nothing".

    Public on purpose: the point is to open it on any device, including one
    nobody has an account on.
    """
    return render(request, "sensorlab/sensor_check.html")


@sensorlab_login_required
def sensors(request):
    """What this device can measure, and what has been agreed to (spec §2).

    The states are filled in by the browser — only the device can answer
    "is this sensor actually answering?" — so the server ships one slot per
    sensor and the page reports what it finds.
    """
    from .models import SENSORS

    #: Which sensors this screen offers to test. Names are NOT built here:
    #: they used to be, from an English dict, and a Hebrew reader was shown
    #: "Accelerometer" (SL-A2's bug, third appearance). The template resolves
    #: each key through `{{ key|sensor_name }}`, so no view can get it wrong.
    READABLE_HERE = (
        "accelerometer", "linear-accelerometer", "gyroscope",
        "magnetometer", "camera", "microphone",
    )
    shown = [k for k in SENSORS if k in READABLE_HERE]
    return render(request, "sensorlab/sensors.html", {"sensors": shown})


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
    """The member's home: every track, and the labs inside it (SL-B4).

    A track with no published labs is left out rather than listed as empty.
    Showing "Free Fall — 0 labs" tells a student nothing they can act on, and
    the whole-page empty state below says the useful version of the same
    thing. The cost is that a track whose labs are all still drafts
    disappears from this screen, which is the correct answer for a student
    and a mildly surprising one for an author — so the admin, not this page,
    is where authoring progress is read.
    """
    from .models import Track

    tracks = []
    for track in Track.published.prefetch_related("labs"):
        labs = [row for row in track.labs.all() if row.is_published]
        if labs:
            tracks.append({"track": track, "labs": labs, "count": len(labs)})

    return render(request, "sensorlab/tracks.html",
                  {"tracks": tracks, "profile": profile_for(request.user)})


@sensorlab_login_required
def lab_overview(request, slug):
    """One lab, before you commit twelve minutes to it (SL-B4).

    What it is, how long, what it will ask of your phone, and what has to be
    finished first. spec §1 refuses a degradation tier, so "this lab needs
    your accelerometer" belongs *here* — readable before the lab starts, not
    discovered as a refusal halfway through.

    There is deliberately no start action: Epic D builds the runner. A
    primary button over a 404 is this app's recurring failure mode, so the
    page says plainly that it cannot be run yet.
    """
    from django.shortcuts import get_object_or_404

    from .models import LAB_STEPS, Lab

    lab_row = get_object_or_404(
        Lab.published.select_related("track", "prerequisite_lab"), slug=slug
    )
    config = getattr(lab_row, "experiment", None)
    sensors = list(config.sensor_requirements.all()) if config else []

    return render(request, "sensorlab/lab_overview.html", {
        "lab": lab_row,
        "sensors": sensors,
        # From the model, not spelled out here — one definition of spec §3's
        # flow, shared with the assembled API response.
        "steps": LAB_STEPS,
    })


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
