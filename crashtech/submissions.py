"""Turning work in (spec chapter 7).

The shape of this module is set by one sentence from the 2026 feedback:
"it was never clear whether a submission had actually gone through." So
nothing here returns "incomplete". Every path names the specific missing
thing by its own label, before the team presses anything (Rule 11.6).

The other decision worth stating is **where a deliverable's value lives**,
because it is not one field:

- a **video** is a URL and there is no upload path for one at all
  (Rule 7.5). Any host. This single choice turns roughly 26 GB of phone
  video per event into nothing on our disk.
- an **image** or a **file** is an upload, which goes to object storage
  rather than the application disk (Rule 9.5).
- **text** and a **number** are typed, and go in `text_value`.

A number typed against a *measured* challenge is a different thing again:
it is the team's reported result and lands on `Submission.reported_value`,
where the ranking can see it.
"""

from datetime import timedelta
from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.utils import timezone

from .models import Challenge, Submission, SubmissionFile, Team, UploadToken
from .roles import may_see_challenges
from .scoring import points_for, recompute_challenge
from .teams import team_for


class SubmitError(Exception):
    pass


# ----------------------------------------------------------- what is visible


def visible_challenges(user, hackathon):
    """The challenges this person may read (Rule 7.1).

    Returns an empty queryset rather than a count or a greyed-out list
    before kickoff. A participant who can see that there are seven
    challenges knows something they were not meant to know, and a count is
    the leak most easily left in by accident.
    """
    if not may_see_challenges(user, hackathon):
        return hackathon.challenges.none()
    if hackathon.challenges_visible:
        return hackathon.challenges.all()
    # Before kickoff only the people running the event get here, and they
    # see the unpublished ones too, which is the whole point of writing
    # them in advance.
    return hackathon.challenges.all()


def submit_blocker(user, hackathon):
    """Why this person cannot submit, in words, or `None` if they can.

    One function, so every screen gives the same reason. A disabled button
    with no explanation beside it is the 2026 complaint restated.
    """
    from .models import Hackathon

    if hackathon.status == Hackathon.CLOSED:
        return "Submissions closed when the event ended."
    if hackathon.status in (Hackathon.MUSEUM,):
        return "This event is over. Its results are in the museum."
    if not hackathon.challenges_visible:
        return "The challenges open when the event starts."
    if not hackathon.accepts_submissions:
        if hackathon.submission_deadline and timezone.now() > hackathon.submission_deadline:
            return "The submission deadline has passed."
        return "Submissions are not open."
    team = team_for(user, hackathon)
    if team is None:
        return "You need a team before you can submit. A team of one is fine."
    return None


# ------------------------------------------------------------- the checklist


class Row:
    """One line of the submit checklist.

    Carries the deliverable, whatever has already been provided for it,
    and whether it is still outstanding, so a template never has to work
    any of that out.
    """

    def __init__(self, deliverable, provided=None):
        self.deliverable = deliverable
        self.provided = provided
        self.label = deliverable.label
        self.kind = deliverable.kind
        self.required = deliverable.required
        self.help_text = deliverable.help_text
        self.purpose = deliverable.get_purpose_display()
        self.field = f"d{deliverable.pk}"

    @property
    def done(self):
        return self.provided is not None

    @property
    def outstanding(self):
        return self.required and not self.done

    @property
    def value_text(self):
        if self.provided is None:
            return ""
        p = self.provided
        return p.url or p.text_value or (p.file.name.rsplit("/", 1)[-1] if p.file else "")


def checklist(challenge, submission=None):
    """Every declared deliverable, with what is already in, in order."""
    provided = {}
    if submission is not None:
        for item in submission.files.all():
            provided[item.deliverable_id] = item
    return [Row(d, provided.get(d.pk)) for d in challenge.deliverables.all()]


def missing_labels(challenge, submission=None):
    """The names of what is still needed. Names, never a count."""
    return [row.label for row in checklist(challenge, submission) if row.outstanding]


# ----------------------------------------------------------------- submitting


def submission_for(team, challenge):
    if team is None:
        return None
    return Submission.objects.filter(team=team, challenge=challenge).first()


def save_submission(user, team, challenge, *, data=None, files=None):
    """Create or update this team's one submission to this challenge.

    Returns `(submission, created)`, and raises `SubmitError` describing
    everything that was wrong **after** saving everything that was not.

    **Partial is allowed and is the normal case.** A team photographs the
    bench at 2am, pastes the video link at 5am, and types the final number
    at 7am. Refusing anything until everything is present pushes all three
    into the last ten minutes, which is when the wifi is worst.

    **A refusal never costs the team what they already typed**, which is
    the part that took a test failure to see. The first version wrapped
    the whole function in one transaction and raised on the first problem,
    so a team that filled in two fields and ticked "it worked" too early
    lost the two fields along with the claim. At 3am that is the
    difference between a correction and a retyped submission. So the
    writes happen, the problems are collected, and only then does this
    complain.

    What is still refused outright is `claimed_complete` while a required
    deliverable is missing, because that is the claim the points are paid
    on and the one a judge may later spot-check (Rule 7.3). It is refused
    by not being set, not by discarding the submission.
    """
    data = data or {}
    files = files or {}

    if team is None:
        raise SubmitError("You need a team before you can submit.")
    if team.hackathon_id != challenge.hackathon_id:
        raise SubmitError("That challenge belongs to a different event.")

    problems = []

    with transaction.atomic():
        submission, created = Submission.objects.get_or_create(
            challenge=challenge, team=team, defaults={"submitted_by": user},
        )

        # The reported result, for a measured challenge. Decimal rather
        # than float because this number decides who wins and a float
        # would make 10.1 unequal to 10.1.
        if challenge.kind == Challenge.MEASURED:
            raw = (data.get("reported_value") or "").strip()
            if raw:
                try:
                    submission.reported_value = Decimal(raw)
                except (InvalidOperation, ValueError):
                    problems.append(
                        (challenge.metric_name or "The result") + " has to be a number."
                    )

        note = data.get("reported_note")
        if note is not None:
            submission.reported_note = note.strip()

        # Each declared deliverable, satisfied in whichever way its kind
        # means. One bad one does not stop the others landing.
        for deliverable in challenge.deliverables.all():
            field = "d" + str(deliverable.pk)
            value = None

            if deliverable.kind == deliverable.VIDEO:
                url = (data.get(field) or "").strip()
                if url and not url.lower().startswith(("http://", "https://")):
                    problems.append(
                        deliverable.label + " has to be a link starting with https://"
                    )
                elif url:
                    value = {"url": url}
            elif deliverable.kind in (deliverable.IMAGE, deliverable.FILE):
                upload = files.get(field)
                if upload:
                    value = {"file": upload}
            else:
                text = (data.get(field) or "").strip()
                if text:
                    value = {"text_value": text}

            if value is None:
                continue

            existing = submission.files.filter(deliverable=deliverable).first()
            if existing:
                if "file" in value:
                    existing.file = value["file"]
                else:
                    existing.url = value.get("url", "")
                    existing.text_value = value.get("text_value", "")
                existing.save()
            else:
                SubmissionFile.objects.create(
                    submission=submission, deliverable=deliverable, **value,
                )

        # The claim, which is what actually scores a completion challenge.
        # Asked after the files above have landed, so a team that uploads
        # the last thing and ticks the box in one go is allowed to.
        if data.get("claimed_complete"):
            still_missing = missing_labels(challenge, submission)
            if still_missing:
                problems.append(
                    "Before you can say it worked, this challenge still needs: "
                    + ", ".join(still_missing)
                )
            else:
                submission.claimed_complete = True
        elif "claimed_complete" in data:
            submission.claimed_complete = False

        submission.save()

        # Rule 7.4: points land now, on trust. A measured challenge has to
        # recompute everybody's, because one new number can reorder the
        # ranking under teams who did nothing.
        recompute_challenge(challenge)

    submission.refresh_from_db()
    if problems:
        raise SubmitError(" ".join(problems))
    return submission, created


def withdraw(submission):
    submission.verification = Submission.WITHDRAWN
    submission.claimed_complete = False
    submission.save(update_fields=["verification", "claimed_complete", "updated_at"])
    recompute_challenge(submission.challenge)
    return submission


# ------------------------------------------------------------ the phone, 3am


UPLOAD_TOKEN_HOURS = 30  # The event is 24 hours; a token outliving it by a
# little is kinder than one that expires while somebody is walking back to
# the bench.


def upload_token_for(team, challenge):
    """A token the phone can use without signing in (Rule 7.6).

    The laptop is signed in; the phone that photographs the bench is not,
    and making somebody type a password into a phone at 3am is how the
    photograph does not get taken. Reused rather than reissued so the QR
    on screen stays valid if the page is refreshed.
    """
    token, _ = UploadToken.objects.get_or_create(
        team=team, challenge=challenge,
        defaults={"expires_at": timezone.now() + timedelta(hours=UPLOAD_TOKEN_HOURS)},
    )
    if not token.is_valid:
        token.expires_at = timezone.now() + timedelta(hours=UPLOAD_TOKEN_HOURS)
        token.save(update_fields=["expires_at"])
    return token


def image_deliverables(challenge):
    return challenge.deliverables.filter(kind="image")


# --------------------------------------------------------------- own standing


def team_card(team):
    """What a team sees about itself, always (Rule 8.4).

    Its own points, and for each challenge either a number or the reason
    there is no number yet. Never `0` for a creativity challenge awaiting
    a judge, which reads as a failed attempt rather than a pending one
    (Rule 11.8).
    """
    if team is None:
        return {"total": 0, "rows": []}

    rows = []
    total = 0
    for submission in team.submissions.select_related("challenge").prefetch_related("grades"):
        challenge = submission.challenge
        points = points_for(submission)
        total += points
        if challenge.kind == Challenge.CREATIVITY and not submission.grades.exists():
            display, state = "Judged after the event", "wait"
        elif submission.verification == Submission.WITHDRAWN:
            display, state = "Withdrawn", "stop"
        else:
            display, state = str(points), "go"
        rows.append({
            "submission": submission, "challenge": challenge,
            "points": points, "display": display, "state": state,
        })
    return {"total": total, "rows": rows}


# ----------------------------------------------------------- showing a number


def tidy(value):
    """A Decimal as the person typed it, not as the column stores it.

    `reported_value` is `decimal_places=4`, so 188.5 comes back as
    `188.5000` and the field a team opens at 3am shows a number they did
    not type. That reads as the system having changed their result, which
    on the one field that decides the ranking is the worst possible
    impression to give. Four trailing zeros are storage, not data.
    """
    if value is None:
        return ""
    text = format(value, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"


def qr_data_uri(url, box_size=6):
    """The upload link as a QR, inline in the page (Rule 7.6).

    Inline rather than a file or a route: it is one small PNG, it is
    per-team and per-challenge, and writing it to disk or serving it from
    a view would both be more moving parts than the thing deserves.

    Printing the URL as text instead, which is what the first version did,
    quietly defeated the whole feature. The point is that somebody holding
    a phone does not type anything.
    """
    import base64
    import io as _io

    import qrcode

    code = qrcode.QRCode(box_size=box_size, border=2)
    code.add_data(url)
    code.make(fit=True)
    image = code.make_image(fill_color="black", back_color="white")
    buffer = _io.BytesIO()
    image.save(buffer, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode()
