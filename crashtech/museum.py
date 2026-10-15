"""The permanent public page an event ends in (spec chapter 9).

Two ideas run through all of it.

**It assembles itself.** The exhibition, the standings, the certificates
and the numbers all come from what the event already produced. The human
adds photos and a paragraph, and nothing else. Opening a blank page after
a sleepless night is how a museum never gets published, which is what
happened to the 2026 event.

**The exhibition is computed from consent, not copied** (Rule 9.4). Only
teams that gave `exhibition_consent` appear, and withdrawing it removes
the work from display *without deleting anything*. A copied exhibition
would mean a team withdrawing consent next year had to trust somebody to
go and delete a row.
"""

from django.db import transaction
from django.utils import timezone

from .models import Challenge, Hackathon, MuseumPage, MuseumPhoto, Submission
from .scoring import leaderboard
from .submissions import tidy


def page_for(hackathon, create=False):
    """The museum page, which exists only once an event has one."""
    if create:
        page, _ = MuseumPage.objects.get_or_create(hackathon=hackathon)
        return page
    return MuseumPage.objects.filter(hackathon=hackathon).first()


def is_open(hackathon):
    """Rule 9.1: the museum opens on publishing, and then it is permanent.

    Tied to the results being published rather than to a flag somebody has
    to remember to set, because the whole point of Rule 8.5 is that one
    click does all of it.
    """
    return bool(hackathon.results_published_at)


def exhibition(hackathon):
    """The work on show, computed from consent every time (Rule 9.4).

    Returns `[{team, points, pieces: [...]}, ...]`, best first. A team that
    has not consented is simply not in the list, and that is the entire
    mechanism: nothing was copied, so nothing has to be deleted.
    """
    out = []
    for team, points in leaderboard(hackathon):
        if not team.exhibition_consent:
            continue
        pieces = []
        for submission in team.submissions.select_related("challenge").prefetch_related(
            "files__deliverable",
        ):
            shown = [f for f in submission.files.all() if f.url or f.file]
            if not shown and submission.reported_value is None:
                continue
            challenge = submission.challenge
            # A measured entry's achievement IS the number, and without it
            # the exhibition showed a bare challenge title with nothing
            # under it: the one thing this team did best, rendered as a
            # heading and a blank. Found by looking at the page.
            result = ""
            if challenge.kind == Challenge.MEASURED and submission.reported_value is not None:
                result = tidy(submission.reported_value)
                if challenge.metric_unit:
                    result += " " + challenge.metric_unit
                if challenge.metric_name:
                    result = challenge.metric_name + " " + result
            pieces.append({
                "submission": submission,
                "challenge": challenge,
                "files": shown,
                "result": result,
            })
        if pieces:
            out.append({"team": team, "points": points, "pieces": pieces})
    return out


def photos(hackathon, for_admin=False):
    """Rule 9.3: only approved photos are public.

    An admin sees the pending ones too, because somebody has to be able to
    rescue a false rejection, and the check fails closed.
    """
    page = page_for(hackathon)
    if page is None:
        return MuseumPhoto.objects.none()
    rows = page.photos.all()
    if for_admin:
        return rows
    return rows.filter(moderation_status=MuseumPhoto.APPROVED)


@transaction.atomic
def add_photo(hackathon, uploaded, caption="", by=None):
    """One photo, moderated on the way in.

    Returns the row whatever the verdict, because a rejected photo that
    silently vanishes leaves the person who posted it with no idea what
    happened. Only approved ones are ever shown.
    """
    from . import moderation

    page = page_for(hackathon, create=True)
    status, note = moderation.check_image(uploaded)
    return MuseumPhoto.objects.create(
        museum_page=page, image=uploaded, caption=(caption or "").strip()[:200],
        uploaded_by=by, moderation_status=status,
        order=page.photos.count(),
    )


def numbers(hackathon):
    """The handful of figures the page leads with.

    Computed rather than written down, so a museum page cannot quietly
    disagree with the event it describes.
    """
    teams = hackathon.teams.count()
    people = hackathon.roles.filter(role="participant").count()
    submitted = Submission.objects.filter(challenge__hackathon=hackathon).count()
    return {
        "teams": teams,
        "people": people,
        "challenges": hackathon.challenges.count(),
        "submissions": submitted,
        "hours": round(
            (hackathon.ends_at - hackathon.starts_at).total_seconds() / 3600
        ) if hackathon.ends_at and hackathon.starts_at else 0,
    }


@transaction.atomic
def set_consent(team, on):
    """Rule 9.4, and it works in both directions at any time, forever.

    A team that changes its mind in three years changes one boolean and
    the exhibition stops showing their work on the next request. Nothing
    is deleted, so changing it back is equally cheap.
    """
    team.exhibition_consent = bool(on)
    team.save(update_fields=["exhibition_consent"])
    return team


def museums():
    """Every published museum, newest first: the public index of them."""
    return Hackathon.objects.filter(
        results_published_at__isnull=False,
    ).order_by("-starts_at")
