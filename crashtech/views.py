"""CrashTech's pages (docs/crashtech/spec.md chapter 11).

Every view is tagged **planning** or **event** in its docstring, because
they are two different products sharing one visual language
(user_journeys.md §1.1): a planning screen is dense and unhurried on a
laptop; an event screen is one action on a phone at 3am with a queue
forming.
"""

from django.contrib import messages
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from . import mail, readiness
from .decorators import signed_in
from .models import EventRole, Hackathon, Milestone, RoleInvitation
from .next_actions import next_actions_for
from .roles import can, roles_for


def _event(slug):
    return get_object_or_404(Hackathon, slug=slug)


def _require(user, hackathon, capability):
    """One line at the top of every view that needs a role.

    Raising rather than redirecting: a person without the role has no
    screen to be sent to, and a redirect would imply there is one.
    """
    if not can(user, hackathon, capability):
        raise PermissionDenied
    return True


# ------------------------------------------------------------------- public


def home(request):
    """**Planning / public.** The front door.

    Signed out this is the public face (Rule 9.2: reading needs no
    account). Signed in it is the way through to whichever events this
    person has a role on.
    """
    open_events = Hackathon.objects.exclude(status=Hackathon.SETUP).exclude(status=Hackathon.MUSEUM)
    museums = Hackathon.objects.filter(status=Hackathon.MUSEUM)

    mine = []
    if request.user.is_authenticated:
        labels = dict(EventRole.ROLES)
        seen = {}
        for role in EventRole.objects.filter(user=request.user).select_related("hackathon"):
            row = seen.setdefault(role.hackathon_id, {"hackathon": role.hackathon, "roles": []})
            row["roles"].append(labels.get(role.role, role.role))
        mine = list(seen.values())
        if request.user.is_superuser:
            # Rule 4.2: the only way a first admin can exist. Without this
            # the person who can create an event cannot find one.
            for event in Hackathon.objects.all():
                if event.id not in seen:
                    mine.append({"hackathon": event, "roles": ["Site admin"]})

    return render(request, "crashtech/home.html", {
        "open_events": open_events,
        "museums": museums,
        "mine": mine,
        "can_create": request.user.is_authenticated and request.user.is_superuser,
    })


def event_home(request, slug):
    """**Planning.** The role-aware home (Rule 11.3).

    Not a dashboard of statistics. A screen that names the current
    milestone and the next action *this person* owns. Five roles, five
    different answers, from one view.
    """
    hackathon = _event(slug)
    labels = dict(EventRole.ROLES)
    held = roles_for(request.user, hackathon)
    return render(request, "crashtech/event_home.html", {
        "hackathon": hackathon,
        "my_roles": sorted(labels.get(r, r) for r in held),
        "milestones": hackathon.milestones.all(),
        "actions": next_actions_for(request.user, hackathon),
        "can_manage": can(request.user, hackathon, "event_settings"),
    })


# --------------------------------------------------------- creating an event


@signed_in
def event_create(request):
    """**Planning.** Rule 4.2: a site superuser creates an event and becomes
    its first admin.

    This is the only place the chain can start, and it is a deliberate,
    named exception rather than an accident of how the check is written:
    no admin exists yet to appoint one.

    Four fields. Everything that can be decided later is decided later,
    because an event with four fields filled is a thing somebody comes
    back to and a thirty-field form is a thing they abandon.
    """
    if not request.user.is_superuser:
        raise PermissionDenied

    errors = {}
    data = {"name": "", "starts_at": "", "ends_at": ""}
    if request.method == "POST":
        data = {k: (request.POST.get(k) or "").strip() for k in data}
        starts = _parse_dt(data["starts_at"])
        ends = _parse_dt(data["ends_at"])

        if not data["name"]:
            errors["name"] = "Give the event a name."
        if not starts:
            errors["starts_at"] = "When does it start?"
        if not ends:
            errors["ends_at"] = "When does it end?"
        if starts and ends and ends <= starts:
            errors["ends_at"] = "It has to end after it starts."

        if not errors:
            with transaction.atomic():
                hackathon = Hackathon.objects.create(
                    name=data["name"], starts_at=starts, ends_at=ends,
                    submission_deadline=ends,
                )
                EventRole.objects.create(
                    hackathon=hackathon, user=request.user,
                    role=EventRole.ADMIN, granted_by=request.user,
                )
            messages.success(request, "Event created. You are its first admin.")
            return redirect("crashtech:event_home", slug=hackathon.slug)

    return render(request, "crashtech/event_create.html", {"errors": errors, "data": data})


def _parse_dt(value):
    from django.utils.dateparse import parse_datetime

    if not value:
        return None
    parsed = parse_datetime(value)
    if parsed is None:
        return None
    if timezone.is_naive(parsed):
        parsed = timezone.make_aware(parsed)
    return parsed


# -------------------------------------------------------------- settings


@signed_in
def event_settings(request, slug):
    """**Planning.** Rule 11.5 in practice: every setting carries its
    consequence next to it rather than in a help page somewhere.

    "Team size" means nothing on its own. "1 makes this an individual
    event" is the thing an organiser actually needs to know, at the moment
    they are deciding.
    """
    hackathon = _event(slug)
    _require(request.user, hackathon, "event_settings")

    if request.method == "POST":
        hackathon.name = (request.POST.get("name") or hackathon.name).strip()
        hackathon.tagline = (request.POST.get("tagline") or "").strip()
        hackathon.repo_url = (request.POST.get("repo_url") or "").strip()
        hackathon.team_size_max = max(1, int(request.POST.get("team_size_max") or 1))
        hackathon.kits_per_team = max(1, int(request.POST.get("kits_per_team") or 1))
        visibility = request.POST.get("leaderboard_visibility")
        if visibility in dict(Hackathon.LEADERBOARD_VISIBILITY):
            hackathon.leaderboard_visibility = visibility
        hackathon.save()
        messages.success(request, "Saved.")
        return redirect("crashtech:settings", slug=hackathon.slug)

    return render(request, "crashtech/event_settings.html", {
        "hackathon": hackathon, "can_manage": True,
        "visibilities": Hackathon.LEADERBOARD_VISIBILITY,
    })


# ------------------------------------------------------------- milestones


@signed_in
def event_milestones(request, slug):
    """**Planning.** The timeline, and where the kit pickup date lives,
    which is the single date participants care about most before the
    event."""
    hackathon = _event(slug)
    _require(request.user, hackathon, "event_settings")

    if request.method == "POST":
        if request.POST.get("delete"):
            hackathon.milestones.filter(pk=request.POST["delete"]).delete()
        else:
            occurs = _parse_dt(request.POST.get("occurs_at"))
            title = (request.POST.get("title") or "").strip()
            if title and occurs:
                Milestone.objects.create(
                    hackathon=hackathon,
                    kind=request.POST.get("kind") or Milestone.CUSTOM,
                    title=title, occurs_at=occurs,
                    blurb=(request.POST.get("blurb") or "").strip(),
                    order=hackathon.milestones.count(),
                )
        return redirect("crashtech:milestones", slug=hackathon.slug)

    return render(request, "crashtech/event_milestones.html", {
        "hackathon": hackathon, "can_manage": True,
        "milestones": hackathon.milestones.all(),
        "kinds": Milestone.KINDS,
    })


# ------------------------------------------------------------------ people


@signed_in
def event_people(request, slug):
    """**Planning.** The admin's real first task (user_journeys.md 2.1 B).

    The whole design of this screen exists because of one problem: **the
    people being appointed do not have accounts yet.** The tech lead and
    the judges are an academic and an engineer at a sponsor, the busiest
    and least patient people in the system. So an email address is enough
    to grant a role, and the row reads "invited, not yet joined" until they
    arrive.
    """
    hackathon = _event(slug)
    _require(request.user, hackathon, "grant_roles")

    if request.method == "POST":
        if request.POST.get("remove_role"):
            hackathon.roles.filter(pk=request.POST["remove_role"]).delete()
            messages.success(request, "Role removed.")
        elif request.POST.get("cancel_invite"):
            hackathon.invitations.filter(pk=request.POST["cancel_invite"]).delete()
            messages.success(request, "Invitation cancelled.")
        else:
            _invite(request, hackathon)
        return redirect("crashtech:people", slug=hackathon.slug)

    labels = dict(EventRole.ROLES)
    grouped = []
    for value, label in EventRole.ROLES:
        grouped.append({
            "value": value,
            "label": label,
            "holders": hackathon.roles.filter(role=value).select_related("user"),
            "invited": hackathon.invitations.filter(role=value, accepted_at__isnull=True),
        })

    return render(request, "crashtech/event_people.html", {
        "hackathon": hackathon, "can_manage": True,
        "grouped": grouped,
        "roles": EventRole.ROLES,
        "labels": labels,
    })


def _invite(request, hackathon):
    """Grant immediately if the person exists, invite if they do not.

    From the admin's side these are one action, and that is the point: they
    should not have to know or care whether this judge already has an
    account here.
    """
    email = (request.POST.get("email") or "").strip().lower()
    role = request.POST.get("role")
    if not email or role not in dict(EventRole.ROLES):
        messages.error(request, "Enter an email address and pick a role.")
        return

    existing = User.objects.filter(email__iexact=email).first()
    if existing:
        _role, created = EventRole.objects.get_or_create(
            hackathon=hackathon, user=existing, role=role,
            defaults={"granted_by": request.user},
        )
        messages.success(
            request,
            f"{email} now has that role." if created else f"{email} already had that role.",
        )
        return

    invitation, created = RoleInvitation.objects.get_or_create(
        hackathon=hackathon, email=email, role=role,
        defaults={"invited_by": request.user},
    )
    if not created and not invitation.is_pending:
        messages.error(request, f"{email} has already accepted an invitation for that role.")
        return

    accept_url = request.build_absolute_uri(
        f"/crashtech/invite/{invitation.token}/"
    )
    invitation.sent_at = timezone.now()
    invitation.save(update_fields=["sent_at"])
    mail.send_role_invitation(invitation, accept_url)
    messages.success(request, f"Invited {email}. They will hold the role as soon as they join.")


def accept_invitation(request, token):
    """Landing on the link from the invitation email.

    Signed in: the role is granted and they go straight to the event.
    Signed out: they are sent to sign up, and the role is waiting when they
    arrive, because `redeem_for` runs on sign-up by email match.
    """
    invitation = get_object_or_404(RoleInvitation, token=token)
    if not request.user.is_authenticated:
        messages.success(
            request,
            f"Create an account with {invitation.email} and your role on "
            f"{invitation.hackathon.name} will be waiting.",
        )
        return redirect(f"/crashtech/signup/?next=/crashtech/e/{invitation.hackathon.slug}/")

    from .invitations import redeem_for

    redeem_for(request.user)
    if invitation.is_pending and request.user.email.lower() == invitation.email.lower():
        redeem_for(request.user)
    messages.success(request, f"You are on {invitation.hackathon.name}.")
    return redirect("crashtech:event_home", slug=invitation.hackathon.slug)


# --------------------------------------------------------------- lifecycle


@signed_in
def event_readiness(request, slug):
    """**Planning.** Rule 3.4: the advance control is a checklist that
    becomes a button, never a button on its own.

    Going live reveals every challenge to everybody at once and cannot be
    undone. That is not a thing to put behind a control that looks like
    any other control.
    """
    hackathon = _event(slug)
    _require(request.user, hackathon, "advance_lifecycle")
    checks = [(c, readiness.resolve(c.fix_url_name, hackathon))
              for c in readiness.checks_for(hackathon)]
    return render(request, "crashtech/event_readiness.html", {
        "hackathon": hackathon, "can_manage": True,
        "checks": checks,
        "blockers": [c for c, _u in checks if c.is_blocker],
        "can_advance": readiness.can_advance(hackathon),
        "consequence": readiness.consequence_of_advancing(hackathon),
        "next_label": dict(Hackathon.STATUSES).get(hackathon.next_status, ""),
    })


@require_POST
@signed_in
def event_advance(request, slug):
    """The transition itself, re-checked server side.

    The checklist hid the control, and that is a courtesy to the person
    rather than a security boundary: the refusal has to live here too, or
    a stale tab is enough to open an event half-written.
    """
    hackathon = _event(slug)
    _require(request.user, hackathon, "advance_lifecycle")

    if not readiness.can_advance(hackathon):
        messages.error(request, "That is still blocked. The checklist says what by.")
        return redirect("crashtech:readiness", slug=hackathon.slug)

    nxt = hackathon.next_status
    with transaction.atomic():
        hackathon.status = nxt
        fields = ["status"]
        if nxt == Hackathon.LIVE:
            # Rule 3.2: every challenge becomes visible at once.
            hackathon.challenges.update(visible=True)
        if nxt == Hackathon.MUSEUM:
            hackathon.results_published_at = timezone.now()
            fields.append("results_published_at")
        hackathon.save(update_fields=fields)

    messages.success(request, f"Now: {dict(Hackathon.STATUSES)[nxt]}.")
    return redirect("crashtech:event_home", slug=hackathon.slug)


# ----------------------------------------------------------------- errors


def not_found(request, exception=None):
    return render(request, "crashtech/404.html", status=404)


def forbidden(request, exception=None):
    return render(request, "crashtech/403.html", status=403)
