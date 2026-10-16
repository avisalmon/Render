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
from django.shortcuts import get_object_or_404, redirect
from django.shortcuts import render as _django_render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from . import (
    judging, kit, mail, museum, naming, readiness, roles, scoring, submissions,
    teams,
)
from .decorators import signed_in
from django.db import models

from .models import (
    Certificate, Challenge, Deliverable, EventRole, Hackathon, KitIssue,
    KitItem, Milestone, MuseumPhoto, Registration, RoleInvitation,
    Submission, SubmissionFile, Team, UploadToken,
)
from .next_actions import next_actions_for
from .roles import can, roles_for


def render(request, template, context=None, status=None):
    """Every CrashTech page, rendered in its event's own timezone.

    The project runs in UTC, so a kickoff at 10:00 in Haifa was printed as
    07:00 or 08:00 depending on the season, on the one product where the
    time on the screen is what people plan a sleepless night around
    (Rule 12.3: the audience is international, so the zone is named too).

    One wrapper rather than a line in every view, because the view that
    forgot would be the one somebody read the wrong kickoff time from.
    """
    hackathon = (context or {}).get("hackathon")
    if hackathon is None:
        return _django_render(request, template, context, status=status)
    with timezone.override(hackathon.tz):
        return _django_render(request, template, context, status=status)


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
    my_registration = None
    if request.user.is_authenticated:
        my_registration = hackathon.registrations.filter(user=request.user).first()

    # The repository opens at kit stage, to the people who were accepted
    # and to the people running the event (Avi's milestone 2, and the
    # consequence the KITS transition already promises in words). The
    # first version stored the link and showed it to nobody.
    accepted = bool(my_registration and my_registration.status == Registration.ACCEPTED)
    staff = bool(held - {EventRole.PARTICIPANT})
    reached_kits = hackathon.status in (
        Hackathon.KITS, Hackathon.LIVE, Hackathon.CLOSED, Hackathon.MUSEUM,
    )
    show_repo = bool(hackathon.repo_url) and reached_kits and (accepted or staff)

    from . import clock

    results = []
    if hackathon.results_published_at:
        results = scoring.standings(hackathon)[:3]

    return render(request, "crashtech/event_home.html", {
        "show_repo": show_repo,
        "pages": _visible_pages(hackathon),
        "schedule": hackathon.schedule.all(),
        "sponsors": hackathon.sponsors.all(),
        "deadline_left": (
            clock.remaining(hackathon.submission_deadline)
            if hackathon.status == Hackathon.LIVE else ""
        ),
        "kickoff_left": (
            clock.remaining(hackathon.starts_at)
            if hackathon.status in (Hackathon.SETUP, Hackathon.PUBLISHED, Hackathon.KITS) else ""
        ),
        "hours": round((hackathon.ends_at - hackathon.starts_at).total_seconds() / 3600),
        "results": results,
        "my_registration": my_registration,
        "can_apply": (
            request.user.is_authenticated
            and hackathon.accepts_registrations
            and my_registration is None
            and roles.may_compete(request.user, hackathon)
        ),
        "needs_name": (
            request.user.is_authenticated and not naming.has_name(request.user)
        ),
        "hackathon": hackathon,
        "my_roles": sorted(labels.get(r, r) for r in held),
        "milestones": hackathon.milestones.all(),
        "actions": next_actions_for(request.user, hackathon),
        "can_manage": can(request.user, hackathon, "event_settings"),
    })


_STAGE_ORDER = [
    Hackathon.SETUP, Hackathon.PUBLISHED, Hackathon.KITS,
    Hackathon.LIVE, Hackathon.CLOSED, Hackathon.MUSEUM,
]
_STAGE_OF_MILESTONE = {
    "publication": Hackathon.PUBLISHED, "hardware": Hackathon.KITS,
    "kickoff": Hackathon.LIVE, "close": Hackathon.CLOSED, "museum": Hackathon.MUSEUM,
}


def _visible_pages(hackathon):
    """The event's own pages, About and Rules, once they are due.

    Modelled in C.1 and seeded with the text that explains trust scoring to
    a participant, and then shown nowhere. `visible_from` lets a page wait
    for a milestone, so a page about the kit can appear at kit stage.
    """
    reached = _STAGE_ORDER.index(hackathon.status)
    out = []
    for page in hackathon.pages.filter(published=True).order_by("order", "id"):
        due = _STAGE_OF_MILESTONE.get(page.visible_from)
        if due is None or _STAGE_ORDER.index(due) <= reached:
            out.append(page)
    return out


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
        starts = _parse_dt(data["starts_at"], Hackathon().tz)
        ends = _parse_dt(data["ends_at"], Hackathon().tz)

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


def _parse_dt(value, tz=None):
    """A typed date and time, read in the event's timezone.

    A browser's datetime field carries no zone at all, so "10:00" means
    10:00 where the event is. Reading it as UTC, which is what this did,
    moved every milestone by two or three hours.
    """
    from django.utils.dateparse import parse_datetime

    if not value:
        return None
    parsed = parse_datetime(value)
    if parsed is None:
        return None
    if timezone.is_naive(parsed):
        parsed = timezone.make_aware(parsed, tz or Hackathon().tz)
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

    errors = {}
    if request.method == "POST":
        zone = (request.POST.get("timezone_name") or hackathon.timezone_name).strip()
        try:
            from zoneinfo import ZoneInfo

            ZoneInfo(zone)
        except Exception:
            errors["timezone_name"] = (
                "Not a timezone name. It looks like Asia/Jerusalem or Europe/Berlin."
            )
            zone = hackathon.timezone_name
        hackathon.timezone_name = zone

        # The dates, which Avi decided come after the event exists: "after
        # we are live we will set dates". They could only be set at
        # creation, so an event could never move.
        starts = _parse_dt(request.POST.get("starts_at"), hackathon.tz) or hackathon.starts_at
        ends = _parse_dt(request.POST.get("ends_at"), hackathon.tz) or hackathon.ends_at
        deadline = (
            _parse_dt(request.POST.get("submission_deadline"), hackathon.tz)
            or hackathon.submission_deadline
        )
        if ends <= starts:
            errors["ends_at"] = "It has to end after it starts."
        elif deadline <= starts:
            errors["submission_deadline"] = "Submissions have to close after the event starts."
        elif deadline > ends:
            errors["submission_deadline"] = (
                "Submissions cannot close after the event ends. They may close before it."
            )
        if errors:
            for message in errors.values():
                messages.error(request, message)
            return redirect("crashtech:settings", slug=hackathon.slug)
        hackathon.starts_at, hackathon.ends_at = starts, ends
        hackathon.submission_deadline = deadline

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
            occurs = _parse_dt(request.POST.get("occurs_at"), hackathon.tz)
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
    if nxt == Hackathon.MUSEUM:
        # Publishing has exactly one door, the publish screen, because it
        # does three permanent things together and this generic transition
        # only did one of them: it opened the museum without freezing the
        # scores or issuing a single certificate. Rule 8.5 is "one gated
        # click", and two doors that do different things is not that.
        return redirect("crashtech:publish", slug=hackathon.slug)

    with transaction.atomic():
        hackathon.status = nxt
        fields = ["status"]
        if nxt == Hackathon.LIVE:
            # Rule 3.2: every challenge becomes visible at once.
            hackathon.challenges.update(visible=True)
        if nxt == Hackathon.CLOSED:
            # Rule 4.6: blind judging needs stable "Entry 1..n" labels, and
            # they are assigned here rather than at team creation so the
            # order carries no information about who signed up first.
            judging.assign_anonymous_labels(hackathon)
        hackathon.save(update_fields=fields)

    messages.success(request, f"Now: {dict(Hackathon.STATUSES)[nxt]}.")
    return redirect("crashtech:event_home", slug=hackathon.slug)


# ----------------------------------------------------------------- errors


def not_found(request, exception=None):
    return render(request, "crashtech/404.html", status=404)


def forbidden(request, exception=None):
    return render(request, "crashtech/403.html", status=403)


# -------------------------------------------------------- registration


@signed_in
@require_POST
def event_apply(request, slug):
    """**Planning / participant.** Rule 5.1: people apply, they are not
    invited.

    The application is its own record, kept apart from the role, so "who
    asked" survives independently of "who is in" and a declined
    application is a fact rather than an absence.
    """
    hackathon = _event(slug)
    if not hackathon.accepts_registrations:
        messages.error(request, "Applications are not open for this event.")
        return redirect("crashtech:event_home", slug=hackathon.slug)
    if not roles.may_compete(request.user, hackathon):
        messages.error(
            request,
            "You can read this event's challenges before it starts, so you "
            "cannot also compete in it.",
        )
        return redirect("crashtech:event_home", slug=hackathon.slug)

    # The name has to exist before anything public can carry it. An
    # account from babook, or from before sign-up asked, may not have one.
    if not naming.has_name(request.user):
        typed = " ".join((request.POST.get("name") or "").split())
        if not typed:
            messages.error(request, "Add your name first. It goes on your certificate.")
            return redirect("crashtech:event_home", slug=hackathon.slug)
        naming.set_name(request.user, typed)

    registration, created = Registration.objects.get_or_create(
        hackathon=hackathon, user=request.user,
        defaults={"note": (request.POST.get("note") or "").strip()},
    )
    if created:
        messages.success(request, "Applied. You will hear when a decision is made.")
    elif registration.status == Registration.WITHDRAWN:
        registration.status = Registration.APPLIED
        registration.save(update_fields=["status"])
        messages.success(request, "Applied again.")
    else:
        messages.success(request, "You have already applied.")
    return redirect("crashtech:event_home", slug=hackathon.slug)


@signed_in
def event_registrations(request, slug):
    """**Planning / admin.** Accept or decline, with a note."""
    hackathon = _event(slug)
    _require(request.user, hackathon, "decide_registrations")

    if request.method == "POST":
        decision = request.POST.get("decision")
        registration = hackathon.registrations.filter(pk=request.POST.get("registration")).first()
        if (
            registration
            and decision == Registration.ACCEPTED
            and not roles.may_compete(registration.user, hackathon)
        ):
            messages.error(
                request,
                f"{registration.user.email} can read the challenges early, "
                "so they cannot also compete.",
            )
            return redirect("crashtech:registrations", slug=hackathon.slug)
        if registration and decision in (Registration.ACCEPTED, Registration.DECLINED):
            registration.status = decision
            registration.decided_at = timezone.now()
            registration.decided_by = request.user
            registration.save(update_fields=["status", "decided_at", "decided_by"])
            if decision == Registration.ACCEPTED:
                # Accepting is what grants the role. The two are separate
                # records on purpose (Rule 5.1).
                EventRole.objects.get_or_create(
                    hackathon=hackathon, user=registration.user,
                    role=EventRole.PARTICIPANT, defaults={"granted_by": request.user},
                )
            else:
                hackathon.roles.filter(
                    user=registration.user, role=EventRole.PARTICIPANT,
                ).delete()
            messages.success(request, f"{registration.user.email}: {decision}.")
        return redirect("crashtech:registrations", slug=hackathon.slug)

    return render(request, "crashtech/event_registrations.html", {
        "hackathon": hackathon, "can_manage": True,
        "waiting": hackathon.registrations.filter(status=Registration.APPLIED).select_related("user"),
        "decided": hackathon.registrations.exclude(status=Registration.APPLIED).select_related("user"),
    })


# --------------------------------------------------------------- teams


@signed_in
def event_teams(request, slug):
    """**Planning.** Form a team or join one.

    The size limit is shown as a fact, not discovered as an error
    (user_journeys.md 2.3): "Teams of up to 3. Yours has 2."
    """
    hackathon = _event(slug)

    if request.method == "POST":
        try:
            if request.POST.get("leave"):
                team = teams.leave_team(request.user, hackathon)
                messages.success(request, f"You have left {team.name}.")
            elif request.POST.get("join"):
                target = get_object_or_404(Team, pk=request.POST["join"], hackathon=hackathon)
                teams.join_team(request.user, hackathon, target)
                messages.success(request, f"You are on {target.name}.")
            else:
                team = teams.create_team(request.user, hackathon, request.POST.get("name"))
                messages.success(request, f"{team.name} is yours.")
        except teams.TeamError as exc:
            messages.error(request, str(exc))
        return redirect("crashtech:teams", slug=hackathon.slug)

    mine = teams.team_for(request.user, hackathon)
    joinable = teams.joinable_teams(hackathon)
    if mine:
        joinable = joinable.exclude(pk=mine.pk)
    return render(request, "crashtech/event_teams.html", {
        "hackathon": hackathon,
        "can_manage": can(request.user, hackathon, "event_settings"),
        "my_team": mine,
        "locked": teams.teams_locked(hackathon),
        "late_solo": teams.late_solo_allowed(hackathon),
        "may_compete": roles.may_compete(request.user, hackathon),
        "accepted": teams.is_accepted(request.user, hackathon),
        "joinable": joinable,
        "all_teams": hackathon.teams.prefetch_related("memberships__user"),
    })


# ----------------------------------------------------------------- kit


@signed_in
def event_kit(request, slug):
    """**Planning / tech lead.** What the hardware is, per event.

    Rule 6.1: FPGA and ESP32 today, a Raspberry Pi next time, with no code
    change. The 2026 platform had a single integer and could not express
    any of it.
    """
    hackathon = _event(slug)
    _require(request.user, hackathon, "define_kit")

    if request.method == "POST":
        if request.POST.get("delete"):
            hackathon.kit_items.filter(pk=request.POST["delete"]).delete()
        else:
            name = (request.POST.get("name") or "").strip()
            if name:
                KitItem.objects.create(
                    hackathon=hackathon, name=name,
                    description=(request.POST.get("description") or "").strip(),
                    quantity_total=max(0, int(request.POST.get("quantity_total") or 0)),
                    is_returnable=bool(request.POST.get("is_returnable")),
                    order=hackathon.kit_items.count(),
                )
        return redirect("crashtech:kit", slug=hackathon.slug)

    return render(request, "crashtech/event_kit.html", {
        "hackathon": hackathon,
        "can_manage": can(request.user, hackathon, "event_settings"),
        "items": hackathon.kit_items.all(),
    })


@signed_in
def event_kit_desk(request, slug):
    """**Event screen.** The desk, with a queue in front of it.

    Everything about this screen is the five-second target: one search
    field focused on arrival, big rows, a single tap for a team of one,
    and back to an empty search ready for the next person. No JavaScript,
    because the corridor it runs in has the worst wifi of the event.
    """
    hackathon = _event(slug)
    _require(request.user, hackathon, "distribute_kits")

    if request.method == "POST":
        team = get_object_or_404(Team, pk=request.POST.get("team"), hackathon=hackathon)
        try:
            if request.POST.get("take_back"):
                issue = team.kit_issues.filter(status=KitIssue.COLLECTED).first()
                if issue:
                    kit.take_back(issue)
                messages.success(request, f"{team.name}: kit back in the box.")
            else:
                member_id = request.POST.get("member")
                members = kit.collectors_for(team)
                collector = next((m for m in members if str(m.pk) == str(member_id)), None)
                if collector is None and len(members) == 1:
                    collector = members[0]
                kit.give_kit(team, collector, request.user)
                who = collector.email if collector else "the team"
                messages.success(request, f"{team.name}: kit given to {who}.")
        except kit.KitError as exc:
            messages.error(request, str(exc))
        # Back to an empty search, ready for the next person in the queue.
        return redirect("crashtech:kit_desk", slug=hackathon.slug)

    query = request.GET.get("q", "")
    rows = []
    for team in kit.search_teams(hackathon, query):
        rows.append({
            "team": team,
            "members": kit.collectors_for(team),
            "status": kit.status_of(team),
        })

    return render(request, "crashtech/event_kit_desk.html", {
        "hackathon": hackathon, "can_manage": True,
        "query": query, "rows": rows, "counts": kit.counts_for(hackathon),
    })


# --------------------------------------------------------------- challenges


def _challenge(hackathon, pk):
    return get_object_or_404(Challenge, pk=pk, hackathon=hackathon)


@signed_in
def event_challenges(request, slug):
    """**Planning or event, depending entirely on who is reading.**

    One route, three genuinely different screens, which is why it is one
    view: a tech lead writing them, a participant working through them, a
    judge reading them after the close. Splitting it into three URLs would
    mean three places where the secrecy rule could be got wrong.

    Before kickoff a participant gets a screen with **no count on it**
    (Rule 7.1). Not a greyed-out list, not "7 challenges", nothing. A
    number is the leak most easily left in by accident.
    """
    hackathon = _event(slug)
    may_read = roles.may_see_challenges(request.user, hackathon)
    may_author = can(request.user, hackathon, "author_challenges")

    team = teams.team_for(request.user, hackathon)
    blocker = submissions.submit_blocker(request.user, hackathon)
    rows = []
    if may_read:
        mine = {}
        if team is not None:
            mine = {s.challenge_id: s for s in team.submissions.prefetch_related("grades", "files")}
        for challenge in hackathon.challenges.prefetch_related("deliverables"):
            submission = mine.get(challenge.pk)
            rows.append({
                "challenge": challenge,
                "submission": submission,
                "missing": submissions.missing_labels(challenge, submission),
                "submitted": challenge.submissions.count(),
                "points": scoring.points_for(submission) if submission else None,
                "awaiting_judge": (
                    challenge.kind == Challenge.CREATIVITY
                    and submission is not None
                    and not submission.grades.exists()
                ),
            })

    return render(request, "crashtech/event_challenges.html", {
        "hackathon": hackathon,
        "can_manage": can(request.user, hackathon, "event_settings"),
        "may_read": may_read,
        "may_author": may_author,
        "rows": rows,
        "my_team": team,
        "blocker": blocker,
        "card": submissions.team_card(team),
        "secret": not hackathon.challenges_visible,
        "kickoff": hackathon.milestones.filter(kind=Milestone.KICKOFF).first(),
    })


@signed_in
def challenge_edit(request, slug, pk=None):
    """**Planning / tech lead.** Writing one challenge.

    The kind picker explains itself on the screen rather than in a manual
    (Rule 7.2), because the choice between the three is the single most
    consequential decision a tech lead makes and it is not obvious from
    three words. `measured` is the one the 2026 feedback actually asked
    for, so the screen says so.
    """
    hackathon = _event(slug)
    _require(request.user, hackathon, "author_challenges")
    challenge = _challenge(hackathon, pk) if pk else None

    if request.method == "POST":
        if request.POST.get("delete") and challenge:
            if challenge.submissions.exists():
                messages.error(
                    request,
                    "Teams have already submitted to this challenge, so it stays. "
                    "Deleting it would delete their work.",
                )
                return redirect("crashtech:challenge_edit", slug=hackathon.slug, pk=challenge.pk)
            challenge.delete()
            messages.success(request, "Challenge deleted.")
            return redirect("crashtech:challenges", slug=hackathon.slug)

        if request.POST.get("add_deliverable") and challenge:
            label = (request.POST.get("label") or "").strip()
            if label:
                Deliverable.objects.create(
                    challenge=challenge, label=label,
                    kind=request.POST.get("kind") or Deliverable.FILE,
                    purpose=request.POST.get("purpose") or Deliverable.ARTIFACT,
                    required=bool(request.POST.get("required")),
                    help_text=(request.POST.get("help_text") or "").strip(),
                    order=challenge.deliverables.count(),
                )
            return redirect("crashtech:challenge_edit", slug=hackathon.slug, pk=challenge.pk)

        if request.POST.get("drop_deliverable") and challenge:
            item = challenge.deliverables.filter(pk=request.POST["drop_deliverable"]).first()
            if item and item.files.exists():
                # The cascade would delete every file every team turned in
                # for it, mid-event, with no warning. The same rule as
                # deleting a challenge somebody has submitted to.
                messages.error(
                    request,
                    f"{item.files.count()} team(s) have already turned in "
                    f'"{item.label}", so it stays. Removing it would delete their work. '
                    "Untick Required instead if it should stop being asked for.",
                )
            elif item:
                item.delete()
            return redirect("crashtech:challenge_edit", slug=hackathon.slug, pk=challenge.pk)

        title = (request.POST.get("title") or "").strip()
        if not title:
            messages.error(request, "A challenge needs a title.")
        else:
            if challenge is None:
                challenge = Challenge(
                    hackathon=hackathon, created_by=request.user,
                    order=hackathon.challenges.count(),
                    # Rule 7.1: written in advance, invisible until kickoff.
                    # Never default to visible, whatever the event's status.
                    visible=False,
                )
            challenge.title = title
            challenge.brief = (request.POST.get("brief") or "").strip()
            challenge.kind = request.POST.get("kind") or Challenge.COMPLETION
            challenge.points = max(0, int(request.POST.get("points") or 0))
            challenge.metric_name = (request.POST.get("metric_name") or "").strip()
            challenge.metric_unit = (request.POST.get("metric_unit") or "").strip()
            challenge.metric_direction = (
                request.POST.get("metric_direction") or Challenge.HIGHER
            )
            challenge.rank_points = _parse_rank_points(request.POST.get("rank_points"))
            challenge.max_grade = max(1, int(request.POST.get("max_grade") or 10))
            challenge.criteria = (request.POST.get("criteria") or "").strip()
            challenge.save()
            scoring.recompute_challenge(challenge)
            messages.success(request, challenge.title + " saved.")
            return redirect("crashtech:challenge_edit", slug=hackathon.slug, pk=challenge.pk)

    return render(request, "crashtech/challenge_edit.html", {
        "hackathon": hackathon,
        "can_manage": can(request.user, hackathon, "event_settings"),
        "challenge": challenge,
        "deliverables": challenge.deliverables.all() if challenge else [],
        "kinds": Challenge.KINDS,
        "deliverable_kinds": Deliverable.KINDS,
        "purposes": Deliverable.PURPOSES,
        "directions": Challenge.DIRECTIONS,
        "rank_points_text": ", ".join(str(n) for n in (challenge.rank_points if challenge else [])),
    })


def _parse_rank_points(raw):
    """Turn "50, 30, 20" into [50, 30, 20], forgiving about how it was typed.

    A tech lead types this once, under time pressure, and the difference
    between a comma and a space should not be a validation error.
    """
    out = []
    for piece in (raw or "").replace(",", " ").split():
        try:
            out.append(max(0, int(piece)))
        except ValueError:
            continue
    return out


@signed_in
def challenge_preview(request, slug, pk):
    """**Planning / tech lead.** Exactly what a participant will see.

    Its own route rather than a flag on the authoring screen, because the
    point is to look at the participant's screen and not at a rendering of
    the editor (user_journeys.md 2.2). A challenge is written days early
    and read once, at speed, by somebody who has twenty-four hours. This
    is the only chance to notice that the brief never says what to
    actually submit.
    """
    hackathon = _event(slug)
    _require(request.user, hackathon, "author_challenges")
    challenge = _challenge(hackathon, pk)
    return render(request, "crashtech/challenge_submit.html", {
        "hackathon": hackathon,
        "can_manage": can(request.user, hackathon, "event_settings"),
        "challenge": challenge,
        "submission": None,
        "checklist": submissions.checklist(challenge, None),
        "missing": submissions.missing_labels(challenge, None),
        "blocker": None,
        "preview": True,
        "my_team": None,
        "upload_token": None,
        "upload_url": None,
        "upload_qr": None,
        "reported_text": "",
    })


@signed_in
def challenge_submit(request, slug, pk):
    """**Event screen.** Turning work in, at 3am, on bad wifi.

    A checklist, not a form: every declared deliverable on screen with
    either what is already in or its own name as the thing still needed
    (Rule 11.6). Saving part of it is normal and expected, because the
    alternative pushes every team into the last ten minutes.
    """
    hackathon = _event(slug)
    if not roles.may_see_challenges(request.user, hackathon):
        raise PermissionDenied
    challenge = _challenge(hackathon, pk)
    team = teams.team_for(request.user, hackathon)
    blocker = submissions.submit_blocker(request.user, hackathon)

    if request.method == "POST":
        if blocker:
            messages.error(request, blocker)
            return redirect("crashtech:challenge_submit", slug=hackathon.slug, pk=challenge.pk)
        try:
            submission, _created = submissions.save_submission(
                request.user, team, challenge,
                data=request.POST, files=request.FILES,
            )
        except submissions.SubmitError as exc:
            messages.error(request, str(exc))
        else:
            # Rule 11.6: what landed, named, and what it is worth. Never
            # "submitted successfully" with nothing to check it against.
            still = submissions.missing_labels(challenge, submission)
            if still:
                messages.success(request, "Saved. Still needed: " + ", ".join(still))
            elif challenge.kind == Challenge.CREATIVITY:
                messages.success(
                    request,
                    "Saved, and complete. This one is graded by judges after the event.",
                )
            else:
                messages.success(
                    request,
                    "Saved, and complete. "
                    + str(scoring.points_for(submission))
                    + " points on the board.",
                )
        return redirect("crashtech:challenge_submit", slug=hackathon.slug, pk=challenge.pk)

    submission = submissions.submission_for(team, challenge)
    token = qr = upload_url = None
    if team is not None and submissions.image_deliverables(challenge).exists():
        token = submissions.upload_token_for(team, challenge)
        upload_url = request.build_absolute_uri(
            reverse("crashtech:upload_by_token", args=[token.token]),
        )
        qr = submissions.qr_data_uri(upload_url)

    return render(request, "crashtech/challenge_submit.html", {
        "hackathon": hackathon,
        "can_manage": can(request.user, hackathon, "event_settings"),
        "challenge": challenge,
        "submission": submission,
        "checklist": submissions.checklist(challenge, submission),
        "missing": submissions.missing_labels(challenge, submission),
        "points": scoring.points_for(submission) if submission else None,
        "blocker": blocker,
        "preview": False,
        "my_team": team,
        "upload_token": token,
        "upload_url": upload_url,
        "upload_qr": qr,
        "reported_text": submissions.tidy(submission.reported_value) if submission else "",
    })


def upload_by_token(request, token):
    """**Event screen, and the only one with no account behind it.**

    The laptop is signed in. The phone that photographs the bench is not,
    and asking somebody to type a password into a phone at 3am is how the
    photograph does not get taken (Rule 7.6). The token carries the team
    and the challenge, so the upload cannot land on the wrong one.
    """
    row = get_object_or_404(UploadToken, token=token)
    if not row.is_valid:
        return render(request, "crashtech/upload_expired.html", {
            "hackathon": row.challenge.hackathon,
        }, status=410)

    challenge = row.challenge
    hackathon = challenge.hackathon
    if not hackathon.accepts_submissions:
        # Rule 7.7 holds on every path in, and this one has no account
        # behind it, so it is the one most easily forgotten. The token
        # lives 30 hours, which outlives the deadline.
        return render(request, "crashtech/upload_expired.html", {
            "hackathon": hackathon, "closed": True,
        }, status=410)
    deliverables = list(submissions.image_deliverables(challenge))
    if request.method == "POST":
        submission, _ = Submission.objects.get_or_create(challenge=challenge, team=row.team)
        saved = []
        for deliverable in deliverables:
            upload = request.FILES.get("d" + str(deliverable.pk))
            if not upload:
                continue
            existing = submission.files.filter(deliverable=deliverable).first()
            if existing:
                existing.file = upload
                existing.save(update_fields=["file"])
            else:
                SubmissionFile.objects.create(
                    submission=submission, deliverable=deliverable, file=upload,
                )
            saved.append(deliverable.label)
        return render(request, "crashtech/upload_done.html", {
            "hackathon": challenge.hackathon, "challenge": challenge,
            "team": row.team, "saved": saved,
        })

    return render(request, "crashtech/upload_by_token.html", {
        "hackathon": challenge.hackathon, "challenge": challenge,
        "team": row.team, "deliverables": deliverables,
    })


@signed_in
def event_standings(request, slug):
    """**Planning.** The leaderboard, which is computed and never stored.

    Gated by `leaderboard_visibility` until results are published, and
    admin-only by default (Rule 8.4). A team's **own** score is not gated
    by this and lives on the challenges screen, because those are two
    different questions and conflating them is what makes an event feel
    like submitting into silence.
    """
    hackathon = _event(slug)
    if not roles.may_see_standings(request.user, hackathon):
        raise PermissionDenied
    return render(request, "crashtech/event_standings.html", {
        "hackathon": hackathon,
        "can_manage": can(request.user, hackathon, "event_settings"),
        "rows": scoring.standings(hackathon),
        "published": bool(hackathon.results_published_at),
        "my_team": teams.team_for(request.user, hackathon),
    })


# ------------------------------------------------- judging, results, publishing


@signed_in
def event_judging(request, slug):
    """**Planning / judge.** A judge's one screen: what is left to do.

    During the event it is locked and says why in words (Rule 8.1). A
    locked screen that does not explain itself reads as broken, and the
    one thing a judge wants to know during the 24 hours is what they are
    waiting for.
    """
    hackathon = _event(slug)
    _require(request.user, hackathon, "read_judging")
    blocker = judging.judging_blocker(hackathon)
    may_grade = can(request.user, hackathon, "judge")

    creativity = hackathon.challenges.filter(kind=Challenge.CREATIVITY)
    work = []
    if not blocker:
        for challenge in creativity.prefetch_related("submissions__grades"):
            entries = challenge.submissions.exclude(verification=Submission.WITHDRAWN)
            finalists = [s for s in entries if s.is_finalist]
            ungraded = [s for s in finalists if not s.grades.exists()]
            work.append({
                "challenge": challenge,
                "entries": len(entries),
                "finalists": len(finalists),
                "ungraded": len(ungraded),
            })

    return render(request, "crashtech/event_judging.html", {
        "hackathon": hackathon,
        "can_manage": can(request.user, hackathon, "event_settings"),
        "blocker": blocker,
        "may_grade": may_grade,
        "work": work,
        "spot_checks": len(judging.spot_check_queue(hackathon)) if not blocker else 0,
        "challenges": hackathon.challenges.all(),
    })


@signed_in
def challenge_shortlist(request, slug, pk):
    """**Planning / judge.** Rule 8.2, step one, as a comparison.

    Every entry on one screen rather than one at a time, because
    shortlisting *is* a comparison: the question is not "is this good" but
    "is this one of the fifteen worth real attention". One at a time turns
    it into seventy separate verdicts, which is the thing the two-step
    exists to avoid.

    Blind (Rule 4.6): the team is "Entry 7" here, and a name would decide
    it before the work did.
    """
    hackathon = _event(slug)
    _require(request.user, hackathon, "read_judging")
    challenge = _challenge(hackathon, pk)
    blocker = judging.judging_blocker(hackathon)
    may_grade = can(request.user, hackathon, "judge")

    if request.method == "POST":
        if not may_grade:
            raise PermissionDenied
        if blocker:
            messages.error(request, blocker)
            return redirect("crashtech:shortlist", slug=hackathon.slug, pk=challenge.pk)
        submission = get_object_or_404(
            Submission, pk=request.POST.get("submission"), challenge=challenge,
        )
        try:
            judging.set_finalist(submission, request.user, on=bool(request.POST.get("on")))
        except judging.JudgingError as exc:
            messages.error(request, str(exc))
        return redirect("crashtech:shortlist", slug=hackathon.slug, pk=challenge.pk)

    entries = []
    for submission in judging.shortlist_for(challenge):
        entries.append({
            "submission": submission,
            "files": list(submission.files.all()),
            "my_grade": judging.my_grade(submission, request.user),
        })
    return render(request, "crashtech/challenge_shortlist.html", {
        "hackathon": hackathon,
        "can_manage": can(request.user, hackathon, "event_settings"),
        "challenge": challenge, "entries": entries, "blocker": blocker,
        "may_grade": may_grade,
    })


@signed_in
def submission_grade(request, slug, pk):
    """**Planning / judge.** Rule 8.2, step two: one entry, real attention.

    The criteria are on the screen, because a grade given against
    remembered criteria is a different grade from one given against the
    written ones, and the team was told what they were.
    """
    hackathon = _event(slug)
    _require(request.user, hackathon, "read_judging")
    submission = get_object_or_404(Submission, pk=pk, challenge__hackathon=hackathon)
    blocker = judging.judging_blocker(hackathon)
    may_grade = can(request.user, hackathon, "judge")

    if request.method == "POST":
        if not may_grade:
            raise PermissionDenied
    if request.method == "POST" and not blocker:
        try:
            judging.grade(
                submission, request.user,
                request.POST.get("grade"), request.POST.get("note"),
            )
            messages.success(request, f"Graded {submission.team.anon_label}.")
            return redirect("crashtech:shortlist", slug=hackathon.slug,
                            pk=submission.challenge.pk)
        except judging.JudgingError as exc:
            messages.error(request, str(exc))

    return render(request, "crashtech/submission_grade.html", {
        "hackathon": hackathon,
        "can_manage": can(request.user, hackathon, "event_settings"),
        "submission": submission, "challenge": submission.challenge,
        "files": list(submission.files.select_related("deliverable")),
        "mine": judging.my_grade(submission, request.user),
        "others": submission.grades.exclude(judge=request.user).select_related("judge"),
        "blocker": blocker, "may_grade": may_grade,
    })


@signed_in
def event_verify(request, slug):
    """**Planning / judge.** Rule 8.3, and the screen most easily got wrong.

    It shows the top few scores per measured challenge and nothing else.
    Listing every submission here would be read as an instruction to check
    every submission, and the trust model would have quietly become the
    2026 one it replaced. The screen says so in as many words.
    """
    hackathon = _event(slug)
    _require(request.user, hackathon, "read_judging")
    blocker = judging.judging_blocker(hackathon)
    may_grade = can(request.user, hackathon, "judge")

    if request.method == "POST":
        if not may_grade:
            raise PermissionDenied
    if request.method == "POST" and not blocker:
        submission = get_object_or_404(
            Submission, pk=request.POST.get("submission"), challenge__hackathon=hackathon,
        )
        try:
            judging.verify(
                submission, request.user,
                request.POST.get("outcome"), request.POST.get("note"),
            )
            messages.success(request, f"{submission.team.anon_label}: recorded.")
        except judging.JudgingError as exc:
            messages.error(request, str(exc))
        return redirect("crashtech:verify", slug=hackathon.slug)

    # Grouped by challenge rather than one flat list: with two measured
    # challenges the flat version repeated the same heading six times, which
    # buries the one thing that distinguishes the rows.
    groups = []
    if not blocker:
        by_challenge = {}
        for submission in judging.spot_check_queue(hackathon):
            by_challenge.setdefault(submission.challenge_id, {
                "challenge": submission.challenge, "rows": [],
            })["rows"].append({
                "submission": submission,
                "value": submissions.tidy(submission.reported_value),
                "points": scoring.points_for(submission),
                "files": list(submission.files.select_related("deliverable")),
            })
        groups = list(by_challenge.values())
    return render(request, "crashtech/event_verify.html", {
        "hackathon": hackathon,
        "can_manage": can(request.user, hackathon, "event_settings"),
        "groups": groups, "blocker": blocker, "may_grade": may_grade,
    })


@signed_in
def event_publish(request, slug):
    """**Planning / admin.** The one gated click (Rule 8.5, 11.7).

    Three permanent effects at once, named in words before the button, and
    gated on conditions that are computed rather than tracked: a stored
    "ready to publish" goes stale the moment a judge disputes something.
    """
    hackathon = _event(slug)
    _require(request.user, hackathon, "advance_lifecycle")
    blockers = judging.publish_blockers(hackathon)

    if request.method == "POST":
        if hackathon.results_published_at:
            messages.error(request, "These results are already published.")
        elif blockers:
            # The screen hid the button, which is a courtesy. The refusal
            # has to live here too, or a stale tab is enough to publish
            # half-judged results permanently.
            messages.error(request, "Publishing is still blocked. The list says by what.")
        else:
            judging.publish(hackathon, by=request.user)
            messages.success(request, "Published. The standings and the museum are open.")
            return redirect("crashtech:standings", slug=hackathon.slug)
        return redirect("crashtech:publish", slug=hackathon.slug)

    return render(request, "crashtech/event_publish.html", {
        "hackathon": hackathon,
        "can_manage": True,
        "blockers": [
            (b, readiness.resolve(b.url_name, hackathon, challenge=b.challenge))
            for b in blockers
        ],
        "consequence": judging.PUBLISH_CONSEQUENCE,
        "rows": scoring.standings(hackathon),
        "published": bool(hackathon.results_published_at),
    })


def certificate(request, cert_id):
    """**Public, permanent, unguessable** (Rule 8.6).

    No account, deliberately: the person who needs to see this is a
    recruiter following a link on a CV two years later, and an account
    wall is how they decide it is not worth it.
    """
    row = get_object_or_404(Certificate, cert_id=cert_id)
    return render(request, "crashtech/certificate.html", {
        "certificate": row, "hackathon": row.hackathon, "team": row.team,
        "members": [m.user for m in row.team.memberships.select_related("user")],
        "points": row.team.submissions.aggregate(
            total=models.Sum("final_points"),
        )["total"] or 0,
    })


# ----------------------------------------------------------------- museum


def event_museum(request, slug):
    """**Public, permanent, and the one screen a stranger meets first.**

    No `@signed_in`, deliberately (Rule 9.2): this is where somebody who
    has never heard of CrashTech lands years later and decides whether the
    next one is worth a weekend. Signing in buys exactly one thing, the
    ability to add a photo.

    Almost all of it assembles itself (Rule 9.1). The exhibition is
    computed from consent on every request, so a team withdrawing it in
    three years disappears from the page without anybody deleting a row.
    """
    hackathon = _event(slug)
    if not museum.is_open(hackathon):
        # Not a 404: the event exists and is public, it just has not
        # finished. Saying so is more useful than pretending it is not
        # there.
        return render(request, "crashtech/museum_closed.html", {
            "hackathon": hackathon,
        }, status=404 if hackathon.status == Hackathon.SETUP else 200)

    page = museum.page_for(hackathon)
    is_admin = can(request.user, hackathon, "event_settings")
    # Certificates were issued and then linked from nowhere at all, so the
    # one artefact somebody puts on a CV could not be found.
    certs = {c.team_id: c for c in hackathon.certificates.all()}

    if request.method == "POST":
        if not request.user.is_authenticated:
            messages.error(request, "Sign in to add a photo.")
            return redirect("crashtech:login")
        upload = request.FILES.get("photo")
        if upload:
            row = museum.add_photo(
                hackathon, upload, request.POST.get("caption"), by=request.user,
            )
            if row.moderation_status == MuseumPhoto.APPROVED:
                messages.success(request, "Added. Thank you.")
            elif row.moderation_status == MuseumPhoto.PENDING:
                # The check failed closed. Saying "pending" rather than
                # "added" is the honest version and stops somebody
                # uploading it four more times.
                messages.success(request, "Added, and waiting on a check. It will appear shortly.")
            else:
                messages.error(request, "That one did not pass the image check.")
        return redirect("crashtech:museum", slug=hackathon.slug)

    return render(request, "crashtech/museum.html", {
        "hackathon": hackathon,
        "page": page,
        "highlights": page.highlights if page else "",
        "numbers": museum.numbers(hackathon),
        "exhibition": museum.exhibition(hackathon),
        "photos": museum.photos(hackathon, for_admin=is_admin),
        "is_admin": is_admin,
        "standings": [
            (place, team, points, certs.get(team.pk))
            for place, team, points in scoring.standings(hackathon)
        ],
    })


@signed_in
def event_museum_edit(request, slug):
    """**Planning / admin.** The paragraph, and the moderation queue.

    The only two things a human adds to a museum. Everything else on that
    page computed itself.
    """
    hackathon = _event(slug)
    _require(request.user, hackathon, "event_settings")
    page = museum.page_for(hackathon, create=True)

    if request.method == "POST":
        if request.POST.get("photo_id"):
            photo = get_object_or_404(
                MuseumPhoto, pk=request.POST["photo_id"], museum_page=page,
            )
            decision = request.POST.get("decision")
            if decision == "drop":
                # Deleting the row deletes its file (Rule 9.5), which is
                # the whole reason this is not a status change.
                photo.image.delete(save=False)
                photo.delete()
                messages.success(request, "Removed, file and all.")
            elif decision in (MuseumPhoto.APPROVED, MuseumPhoto.REJECTED):
                photo.moderation_status = decision
                photo.save(update_fields=["moderation_status"])
                messages.success(request, f"Photo {decision}.")
        else:
            page.highlights = (request.POST.get("highlights") or "").strip()
            page.published = True
            page.published_at = page.published_at or timezone.now()
            page.save(update_fields=["highlights", "published", "published_at"])
            messages.success(request, "Saved.")
        return redirect("crashtech:museum_edit", slug=hackathon.slug)

    return render(request, "crashtech/museum_edit.html", {
        "hackathon": hackathon, "can_manage": True, "page": page,
        "photos": page.photos.all(),
        "open": museum.is_open(hackathon),
        "consenting": hackathon.teams.filter(exhibition_consent=True).count(),
        "teams": hackathon.teams.count(),
    })


@signed_in
def team_consent(request, slug):
    """**Planning / participant.** Rule 9.4, in both directions, forever.

    One boolean. Withdrawing removes the work from the exhibition on the
    next request and deletes nothing, so changing it back is equally
    cheap. That is the whole reason the exhibition is computed rather than
    copied.
    """
    hackathon = _event(slug)
    team = teams.team_for(request.user, hackathon)
    if team is None:
        raise PermissionDenied
    if request.method == "POST":
        museum.set_consent(team, bool(request.POST.get("on")))
        messages.success(
            request,
            "Your work will be shown in the museum."
            if team.exhibition_consent
            else "Your work is no longer shown. Nothing was deleted, and you can turn it back on.",
        )
    return redirect("crashtech:teams", slug=hackathon.slug)


def museum_index(request):
    """**Public.** Every event that finished, newest first."""
    return render(request, "crashtech/museum_index.html", {
        "events": museum.museums(),
    })
