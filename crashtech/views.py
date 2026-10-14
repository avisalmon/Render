"""CrashTech's pages (docs/crashtech/spec.md chapter 11).

Every view here is tagged **planning** or **event** in its docstring,
because they are two different products sharing one visual language
(user_journeys.md §1.1): a planning screen is dense, unhurried and used on
a laptop; an event screen is one action on a phone at 3am with a queue
forming.

SPR-C.1 builds the skeleton only: the public home, the role-aware home
that every signed-in person lands on, and the 404. The screens that do
real work arrive in C.2 onwards.
"""

from django.shortcuts import render

from .models import EventRole, Hackathon
from .roles import roles_for


def home(request):
    """**Planning / public.** The front door.

    Signed out, this is the public face: the events that are open and the
    museums that are permanent (Rule 9.2, "reading needs no account").
    Signed in, it is the way through to whichever events this person has a
    role on.
    """
    open_events = Hackathon.objects.exclude(status=Hackathon.SETUP).exclude(status=Hackathon.MUSEUM)
    museums = Hackathon.objects.filter(status=Hackathon.MUSEUM)

    mine = []
    if request.user.is_authenticated:
        seen = {}
        for role in EventRole.objects.filter(user=request.user).select_related("hackathon"):
            seen.setdefault(role.hackathon_id, {"hackathon": role.hackathon, "roles": []})
            seen[role.hackathon_id]["roles"].append(role.get_role_display())
        mine = list(seen.values())

    return render(request, "crashtech/home.html", {
        "open_events": open_events,
        "museums": museums,
        "mine": mine,
    })


def event_home(request, slug):
    """**Planning.** The role-aware home (Rule 11.3).

    One screen per role, naming the current milestone and the next action
    *this person* owns, rather than a dashboard of statistics. In C.1 it
    establishes the shape and the chrome; the per-role next actions land
    with the features that create them, in C.2 onwards.
    """
    from django.shortcuts import get_object_or_404

    hackathon = get_object_or_404(Hackathon, slug=slug)
    # Display labels, not the stored codes: `tech_lead` is a raw key and a
    # raw key must never reach a reader (Rule 11.6's cousin).
    labels = dict(EventRole.ROLES)
    mine = sorted(labels.get(r, r) for r in roles_for(request.user, hackathon))
    return render(request, "crashtech/event_home.html", {
        "hackathon": hackathon,
        "my_roles": mine,
        "milestones": hackathon.milestones.all(),
    })


def not_found(request, exception=None):
    """CrashTech's own 404, in CrashTech's own chrome.

    Django allows one project-wide handler, so `mysite/urls.py` composes
    this with the other apps' rather than replacing them (the isolated-app
    pattern in building_an_app.md).
    """
    return render(request, "crashtech/404.html", status=404)
