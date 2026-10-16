"""CrashTech's data (docs/crashtech/data_model.md, approved 2026-10-14).

Eight groups, in the order the spec introduces them: the event and its
milestones, people and roles, hardware, content, challenges, submissions,
judging and the museum, and research.

The only foreign key out of this file is to `settings.AUTH_USER_MODEL`
(spec Rule 2.1.1). Nothing here is shared with `app/`, `matazim/`,
`memz/`, `ustrip/` or `sensorlab/`, and nothing there is read from here.

Two things in this file are deliberately *not* models, and both for the
same reason: a stored copy of something derivable is a second source of
truth that goes stale. The **leaderboard** is computed from submissions
(Rule 8.4), and **readiness** to advance the lifecycle is computed from
whatever is currently outstanding (Rule 3.5).
"""

import secrets
import uuid as _uuid

from django.conf import settings
from django.db import models

from .storage import media_storage
from django.utils import timezone
from django.utils.text import slugify

USER = settings.AUTH_USER_MODEL

# Reverse accessors are prefixed `ct_` rather than `crashtech_` because the
# 2026 platform still living in `app/` already claims `crashtech_roles` and
# `crashtech_teams` on `User`. It is reference and we do not touch it
# (Rule 13.1), so this side moves aside. The prefix goes when it retires.


def new_token(nbytes=24):
    return secrets.token_urlsafe(nbytes)


# --------------------------------------------------- the event and its spine


class Hackathon(models.Model):
    """One event. The root of everything (spec chapter 3)."""

    SETUP, PUBLISHED, KITS, LIVE, CLOSED, MUSEUM = (
        "setup", "published", "kits", "live", "closed", "museum",
    )
    STATUS_ORDER = [SETUP, PUBLISHED, KITS, LIVE, CLOSED, MUSEUM]
    STATUSES = [
        (SETUP, "Setup"), (PUBLISHED, "Published"), (KITS, "Kit distribution"),
        (LIVE, "Live"), (CLOSED, "Closed"), (MUSEUM, "Museum"),
    ]

    INDIVIDUAL_DEFAULT_TEAM_SIZE = 2

    ADMINS_ONLY, PARTICIPANTS, PUBLIC = "admins", "participants", "public"
    LEADERBOARD_VISIBILITY = [
        (ADMINS_ONLY, "Admins only"), (PARTICIPANTS, "Participants"), (PUBLIC, "Public"),
    ]

    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=120, unique=True, blank=True)
    tagline = models.CharField(max_length=200, blank=True, default="")
    status = models.CharField(max_length=10, choices=STATUSES, default=SETUP)

    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()
    # Separate from `ends_at` on purpose: submissions may close before the
    # event itself does (Rule 7.7).
    submission_deadline = models.DateTimeField()
    # An event is a physical place. A UTC-only model gets the pickup day
    # wrong for anybody reading it from another country.
    timezone_name = models.CharField(max_length=64, default="Asia/Jerusalem")

    # Rule 5.2: an int, not a choice. 1 makes the event individual, and
    # there is no ceiling, because the right number is an organiser's
    # decision rather than the software's.
    team_size_max = models.PositiveSmallIntegerField(default=INDIVIDUAL_DEFAULT_TEAM_SIZE)
    # Rule 6.2: how many kits a team is allocated.
    kits_per_team = models.PositiveSmallIntegerField(default=1)

    # Rule 2.2.3 / spec §1.5.1: a pointer and nothing more. Examples,
    # skills and methodology live there; challenges never do.
    repo_url = models.URLField(max_length=500, blank=True, default="")

    # Rule 8.4: a setting, not a policy. A team always sees its own score
    # whatever this says; this governs the *standings*.
    leaderboard_visibility = models.CharField(
        max_length=14, choices=LEADERBOARD_VISIBILITY, default=ADMINS_ONLY,
    )
    # Rule 8.5: set when an admin publishes. Until then the standings exist
    # and almost nobody may see them.
    results_published_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-starts_at", "-id"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.name) or "hackathon"
            slug, i = base, 2
            while Hackathon.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug, i = f"{base}-{i}", i + 1
            self.slug = slug
        super().save(*args, **kwargs)

    # --- the lifecycle (Rule 3.1) ---

    @property
    def tz(self):
        """The event's own timezone, as an object Django can use.

        Falls back to Jerusalem rather than raising, because a mistyped
        zone name should not take an event page down.
        """
        from zoneinfo import ZoneInfo

        try:
            return ZoneInfo(self.timezone_name or "Asia/Jerusalem")
        except Exception:
            return ZoneInfo("Asia/Jerusalem")

    @property
    def is_individual(self):
        return self.team_size_max <= 1

    @property
    def challenges_visible(self):
        """Rule 7.1: invisible until kickoff. Not a hint, not a count."""
        return self.status in (self.LIVE, self.CLOSED, self.MUSEUM)

    @property
    def accepts_registrations(self):
        return self.status in (self.PUBLISHED, self.KITS)

    @property
    def accepts_submissions(self):
        """Rule 7.7: live, and before the deadline, which may fall before
        the event itself ends."""
        return self.status == self.LIVE and timezone.now() <= self.submission_deadline

    @property
    def accepts_judging(self):
        """Rule 8.1: judges do nothing during the event. Grading live would
        score the first submission against a different field from the
        last."""
        return self.status == self.CLOSED

    @property
    def is_published(self):
        return self.status == self.MUSEUM

    @property
    def next_status(self):
        i = self.STATUS_ORDER.index(self.status)
        return self.STATUS_ORDER[i + 1] if i + 1 < len(self.STATUS_ORDER) else None


class Milestone(models.Model):
    """A moment in the event's timeline (Rule 3.6).

    Milestones were narrative until a questionnaire needed to attach to
    one. They are rows because three separate things need them: the
    questionnaire's timing (Rule 10.2), the public timeline, and the
    calendar export. Fixed date fields on `Hackathon` could carry none of
    that, and this is also where the hardware pickup date lives.
    """

    PUBLICATION, HARDWARE, KICKOFF, CLOSE, MUSEUM, CUSTOM = (
        "publication", "hardware", "kickoff", "close", "museum", "custom",
    )
    KINDS = [
        (PUBLICATION, "Publication"), (HARDWARE, "Hardware"), (KICKOFF, "Kickoff"),
        (CLOSE, "Close"), (MUSEUM, "Museum"), (CUSTOM, "Custom"),
    ]

    hackathon = models.ForeignKey(Hackathon, on_delete=models.CASCADE, related_name="milestones")
    kind = models.CharField(max_length=12, choices=KINDS, default=CUSTOM)
    title = models.CharField(max_length=160)
    occurs_at = models.DateTimeField()
    blurb = models.TextField(blank=True, default="")
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["order", "occurs_at", "id"]

    def __str__(self):
        return f"{self.title} ({self.hackathon.slug})"


# ------------------------------------------------------------ people & roles


class EventRole(models.Model):
    """A role grant, scoped to one event (Rule 4.1).

    `tech_lead` and `admin` are separate *jobs*, not necessarily separate
    people: one person may hold both and on a small event usually will.
    Holding two roles is two rows, which costs nothing.
    """

    TECH_LEAD, ADMIN, JUDGE, PARTICIPANT, RESEARCHER = (
        "tech_lead", "admin", "judge", "participant", "researcher",
    )
    ROLES = [
        (TECH_LEAD, "Tech lead"), (ADMIN, "Admin"), (JUDGE, "Judge"),
        (PARTICIPANT, "Participant"), (RESEARCHER, "Researcher"),
    ]

    hackathon = models.ForeignKey(Hackathon, on_delete=models.CASCADE, related_name="roles")
    user = models.ForeignKey(USER, on_delete=models.CASCADE, related_name="ct_roles")
    role = models.CharField(max_length=12, choices=ROLES)
    granted_by = models.ForeignKey(USER, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["role", "created_at"]
        constraints = [
            models.UniqueConstraint(fields=["hackathon", "user", "role"], name="ct_role_unique"),
        ]

    def __str__(self):
        return f"{self.user} is {self.role} on {self.hackathon.slug}"


class RoleInvitation(models.Model):
    """A role granted to an email address, before that person has an
    account (Rule 4.3).

    The admin's first real task is appointing a tech lead and judges, and
    those are busy outsiders who have never heard of this site. Without
    this, that first action waits on three prior steps by somebody else:
    "create an account on a site you do not know, tell me when you are
    done, then I will give you access" loses people.

    It also makes **invited but not joined** a visible state, which is the
    one that matters two days before an event when a judge has not turned
    up.
    """

    hackathon = models.ForeignKey(Hackathon, on_delete=models.CASCADE, related_name="invitations")
    email = models.EmailField()
    role = models.CharField(max_length=12, choices=EventRole.ROLES)
    invited_by = models.ForeignKey(USER, on_delete=models.SET_NULL, null=True, related_name="+")
    token = models.CharField(max_length=64, unique=True, default=new_token)
    sent_at = models.DateTimeField(null=True, blank=True)
    accepted_at = models.DateTimeField(null=True, blank=True)
    accepted_user = models.ForeignKey(USER, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["hackathon", "email", "role"], name="ct_invite_unique"),
        ]

    def __str__(self):
        return f"{self.email} invited as {self.role}"

    @property
    def is_pending(self):
        return self.accepted_at is None


class Registration(models.Model):
    """Somebody asking to take part (Rule 5.1).

    People apply; they are not invited. Kept apart from `EventRole` so that
    "who asked" survives independently of "who is in": accepting is what
    grants the participant role, and a declined application is still a
    record rather than an absence.
    """

    APPLIED, ACCEPTED, DECLINED, WITHDRAWN = "applied", "accepted", "declined", "withdrawn"
    STATUSES = [
        (APPLIED, "Applied"), (ACCEPTED, "Accepted"),
        (DECLINED, "Declined"), (WITHDRAWN, "Withdrawn"),
    ]

    hackathon = models.ForeignKey(Hackathon, on_delete=models.CASCADE, related_name="registrations")
    user = models.ForeignKey(USER, on_delete=models.CASCADE, related_name="ct_registrations")
    status = models.CharField(max_length=10, choices=STATUSES, default=APPLIED)
    note = models.TextField(blank=True, default="")
    applied_at = models.DateTimeField(auto_now_add=True)
    decided_at = models.DateTimeField(null=True, blank=True)
    decided_by = models.ForeignKey(USER, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")

    class Meta:
        ordering = ["applied_at"]
        constraints = [
            models.UniqueConstraint(fields=["hackathon", "user"], name="ct_registration_unique"),
        ]

    def __str__(self):
        return f"{self.user} -> {self.hackathon.slug} ({self.status})"


class Team(models.Model):
    """The thing that competes: one person, or more (Rule 5.2).

    A team of one is still a team, which sounds like pedantry and is not:
    it is what stops the leaderboard, the certificates, the blind judging
    and the museum from each having to ask whether they are looking at a
    person or a group.

    **No captain** (Rule 5.4). Every member holds every authority: any may
    submit, upload, collect the kit, or change anything the team owns.
    """

    hackathon = models.ForeignKey(Hackathon, on_delete=models.CASCADE, related_name="teams")
    name = models.CharField(max_length=120, blank=True, default="")
    members = models.ManyToManyField(USER, through="TeamMembership", related_name="ct_teams")
    # Stable anonymous label for blind judging (Rule 4.6).
    anon_ordinal = models.PositiveIntegerField(default=0)
    # Captured up front, revocable afterwards (Rule 9.4).
    exhibition_consent = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["hackathon", "name"], condition=~models.Q(name=""), name="ct_team_name_unique",
            ),
        ]

    def __str__(self):
        return self.name or f"Team {self.anon_ordinal or self.pk}"

    @property
    def anon_label(self):
        return f"Entry {self.anon_ordinal}" if self.anon_ordinal else "Entry ?"


class TeamMembership(models.Model):
    """Why this exists instead of a plain many-to-many (Rule 5.3).

    A bare M2M says a person may be on any number of teams, anywhere. The
    truth is **no within one event, yes across events**: two teams in the
    same event would mean two scores for one person, two kits, and a
    leaderboard nobody can read; while somebody competing three years
    running has three teams, which is the point of a platform rather than
    one event.

    A plain M2M cannot express that, because the constraint lives on
    (hackathon, user) while the join table only knows (team, user). So the
    hackathon is denormalised onto the membership, for exactly one reason:
    so the database can hold the constraint rather than a view remembering
    to check it.
    """

    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="memberships")
    user = models.ForeignKey(USER, on_delete=models.CASCADE, related_name="ct_memberships")
    hackathon = models.ForeignKey(Hackathon, on_delete=models.CASCADE, related_name="memberships")
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["joined_at"]
        constraints = [
            models.UniqueConstraint(fields=["hackathon", "user"], name="ct_one_team_per_event"),
        ]

    def __str__(self):
        return f"{self.user} in {self.team}"


# ------------------------------------------------------------------ hardware


class KitItem(models.Model):
    """What the kit is made of, defined per event (Rule 6.1).

    The 2026 platform had a single integer, `hardware_stock`, which could
    not express *what* the hardware was and so could never be swapped for
    a Raspberry Pi. This can.
    """

    hackathon = models.ForeignKey(Hackathon, on_delete=models.CASCADE, related_name="kit_items")
    name = models.CharField(max_length=160)
    description = models.TextField(blank=True, default="")
    image = models.ImageField(upload_to="crashtech/kit/", blank=True, null=True)
    quantity_total = models.PositiveIntegerField(default=0)
    # A dev board comes back; a jumper wire does not.
    is_returnable = models.BooleanField(default=True)
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return self.name


class KitIssue(models.Model):
    """Handing a kit over and confirming it arrived (Rule 6.2, 6.3).

    **Allocation and collection are different facts** and one row answers
    both: the kit belongs to the *team*, and it is picked up in person by
    one of its *members*, whoever turned up. Recording which member is not
    bookkeeping for its own sake: the research is about individuals, and
    "who actually fetched the hardware" would otherwise be lost the moment
    the kit became a team asset.
    """

    RESERVED, COLLECTED, RETURNED, LOST = "reserved", "collected", "returned", "lost"
    STATUSES = [
        (RESERVED, "Reserved"), (COLLECTED, "Collected"),
        (RETURNED, "Returned"), (LOST, "Lost"),
    ]

    hackathon = models.ForeignKey(Hackathon, on_delete=models.CASCADE, related_name="kit_issues")
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="kit_issues")
    # Null means "the whole kit" rather than one named item.
    item = models.ForeignKey(KitItem, on_delete=models.SET_NULL, null=True, blank=True, related_name="issues")
    status = models.CharField(max_length=10, choices=STATUSES, default=RESERVED)
    collected_by = models.ForeignKey(USER, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    collected_at = models.DateTimeField(null=True, blank=True)
    confirmed_by = models.ForeignKey(USER, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    note = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["-collected_at", "id"]

    def __str__(self):
        return f"{self.team} kit ({self.status})"


# ------------------------------------------------------------------- content


class ContentPage(models.Model):
    """Per-event prose (spec §1.5.1).

    Deliberately narrow. What the event is, its rules, how to register:
    anything specific to *this* event. **Not** the hardware guide, the
    setup checklist, the AI guidance or the practice projects, which live
    in the supporting repository. A database restating a repo is two
    sources of truth, and they drift the first time somebody fixes a pin
    number in only one of them.
    """

    hackathon = models.ForeignKey(Hackathon, on_delete=models.CASCADE, related_name="pages")
    slug = models.SlugField(max_length=80)
    title = models.CharField(max_length=160)
    body = models.TextField(blank=True, default="")
    # Null means always visible.
    visible_from = models.CharField(max_length=12, choices=Milestone.KINDS, blank=True, default="")
    published = models.BooleanField(default=False)
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]
        constraints = [
            models.UniqueConstraint(fields=["hackathon", "slug"], name="ct_page_slug_unique"),
        ]

    def __str__(self):
        return self.title


class ScheduleItem(models.Model):
    """Structured rather than prose, because it drives the calendar.

    The ICS export is a loop over `Milestone` plus this, which is why both
    are structured and neither is a paragraph of markdown.
    """

    hackathon = models.ForeignKey(Hackathon, on_delete=models.CASCADE, related_name="schedule")
    title = models.CharField(max_length=160)
    description = models.TextField(blank=True, default="")
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField(null=True, blank=True)
    location = models.CharField(max_length=160, blank=True, default="")
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["order", "starts_at", "id"]

    def __str__(self):
        return self.title


class Sponsor(models.Model):
    hackathon = models.ForeignKey(Hackathon, on_delete=models.CASCADE, related_name="sponsors")
    name = models.CharField(max_length=160)
    logo = models.ImageField(upload_to="crashtech/sponsors/", blank=True, null=True)
    url = models.URLField(blank=True, default="")
    tier = models.CharField(max_length=40, blank=True, default="")
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return self.name


# ---------------------------------------------------------------- challenges


class Challenge(models.Model):
    """A task, secret until kickoff (Rule 7.1, 7.2).

    Three kinds, one model, because a submission is the same shape in all
    three cases. `measured` is the one real product response to the 2026
    feedback, where 26% of 79 participants said AI did all the work and the
    8% who praised the optimization challenges explained why: a number is
    either hit or not and cannot be talked into existing.
    """

    COMPLETION, MEASURED, CREATIVITY = "completion", "measured", "creativity"
    KINDS = [
        (COMPLETION, "Completion"), (MEASURED, "Measured"), (CREATIVITY, "Creativity"),
    ]
    HIGHER, LOWER = "higher_is_better", "lower_is_better"
    DIRECTIONS = [(HIGHER, "Higher is better"), (LOWER, "Lower is better")]

    hackathon = models.ForeignKey(Hackathon, on_delete=models.CASCADE, related_name="challenges")
    title = models.CharField(max_length=200)
    brief = models.TextField(blank=True, default="")
    kind = models.CharField(max_length=12, choices=KINDS, default=COMPLETION)
    points = models.PositiveIntegerField(default=0)
    # Rule 7.1: false until kickoff flips them all at once.
    visible = models.BooleanField(default=False)
    order = models.PositiveSmallIntegerField(default=0)
    created_by = models.ForeignKey(USER, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    # --- measured challenges only ---
    metric_name = models.CharField(max_length=80, blank=True, default="")
    metric_unit = models.CharField(max_length=40, blank=True, default="")
    metric_direction = models.CharField(max_length=20, choices=DIRECTIONS, default=HIGHER)
    # Points by finishing position, e.g. [50, 30, 20, 10].
    rank_points = models.JSONField(default=list, blank=True)

    # --- creativity challenges only ---
    max_grade = models.PositiveSmallIntegerField(default=10)
    criteria = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return self.title

    @property
    def is_judged(self):
        """Rule 7.4: creativity scores only when a human has graded it."""
        return self.kind == self.CREATIVITY

    @property
    def is_finished(self):
        """Rule 3.4: a challenge with no required deliverable is not
        finished, and the readiness checklist says so rather than letting
        it look identical to one that is."""
        return self.deliverables.filter(required=True).exists()


class Deliverable(models.Model):
    """What a submission to this challenge must contain (Rule 7.3).

    Declared in advance, which is what lets the app say *what* is still
    missing before a team submits rather than after. In 2026 every
    submission had exactly one zip field, identical for every challenge.
    """

    PROOF, ARTIFACT = "proof", "artifact"
    PURPOSES = [(PROOF, "Proof it worked"), (ARTIFACT, "How it was built")]
    VIDEO, IMAGE, TEXT, NUMBER, FILE = "video", "image", "text", "number", "file"
    KINDS = [
        (VIDEO, "Video (a link)"), (IMAGE, "Image"), (TEXT, "Text"),
        (NUMBER, "Number"), (FILE, "File"),
    ]

    challenge = models.ForeignKey(Challenge, on_delete=models.CASCADE, related_name="deliverables")
    label = models.CharField(max_length=160)
    purpose = models.CharField(max_length=10, choices=PURPOSES, default=ARTIFACT)
    kind = models.CharField(max_length=8, choices=KINDS, default=FILE)
    required = models.BooleanField(default=True)
    help_text = models.CharField(max_length=200, blank=True, default="")
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return self.label

    @property
    def is_link_only(self):
        """Rule 7.5: a demo video is a URL and there is no upload path for
        one. Any host. This is the single decision that turns roughly 26 GB
        of phone video per event into nothing at all."""
        return self.kind == self.VIDEO


# --------------------------------------------------------------- submissions


class Submission(models.Model):
    """What a team turns in, and the trust model (Rule 7.4).

    **The inversion from 2026.** The old `Submission` started `pending`
    with zero points and waited for a judge before it scored anything.
    This one scores on submission and treats verification as a later,
    optional, narrow act aimed only at the handful of scores that decide
    the outcome. `unverified` is a normal, final, respectable state for the
    great majority of submissions, and nothing blocks on a judge.

    **Creativity is the one exception, and it is not an exception to
    trust** (Rule 8.2). It has no number to report and nothing a later spot
    check could compare against, so it scores only on a judge's grade. A
    team cannot report its own originality any more than its own final
    placing.
    """

    UNVERIFIED, VERIFIED, DISPUTED, WITHDRAWN = "unverified", "verified", "disputed", "withdrawn"
    VERIFICATIONS = [
        (UNVERIFIED, "Unverified"), (VERIFIED, "Verified"),
        (DISPUTED, "Disputed"), (WITHDRAWN, "Withdrawn"),
    ]

    challenge = models.ForeignKey(Challenge, on_delete=models.CASCADE, related_name="submissions")
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="submissions")
    # Which individual acted. The research is about individuals, and a team
    # could otherwise hide who did what (Rule 10.5).
    submitted_by = models.ForeignKey(USER, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")

    reported_value = models.DecimalField(max_digits=18, decimal_places=4, null=True, blank=True)
    reported_note = models.TextField(blank=True, default="")
    claimed_complete = models.BooleanField(default=False)

    # Awarded immediately, on trust. Always 0 for creativity.
    tentative_points = models.PositiveIntegerField(default=0)
    # Set when results are confirmed; null until then.
    final_points = models.PositiveIntegerField(null=True, blank=True)

    verification = models.CharField(max_length=12, choices=VERIFICATIONS, default=UNVERIFIED)
    verified_by = models.ForeignKey(USER, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    verified_at = models.DateTimeField(null=True, blank=True)
    verification_note = models.TextField(blank=True, default="")

    # Rule 8.2: shortlisted for judging. Judges do not grade everything.
    is_finalist = models.BooleanField(default=False)
    finalist_set_by = models.ForeignKey(USER, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    finalist_set_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["created_at", "id"]
        constraints = [
            models.UniqueConstraint(fields=["challenge", "team"], name="ct_submission_unique"),
        ]

    def __str__(self):
        return f"{self.team} -> {self.challenge}"

    @property
    def missing_deliverables(self):
        """Rule 11.6: name what is missing, never "incomplete"."""
        provided = set(self.files.values_list("deliverable_id", flat=True))
        return [d for d in self.challenge.deliverables.filter(required=True) if d.id not in provided]

    @property
    def is_complete(self):
        return not self.missing_deliverables


class SubmissionFile(models.Model):
    """One deliverable, satisfied.

    `file` is stored on external object storage, never the application
    disk (Rule 9.5). `url` is how a **video** is always provided, since
    there is no upload path for one at all.
    """

    submission = models.ForeignKey(Submission, on_delete=models.CASCADE, related_name="files")
    deliverable = models.ForeignKey(Deliverable, on_delete=models.CASCADE, related_name="files")
    file = models.FileField(
        upload_to="crashtech/submissions/", blank=True, null=True,
        storage=media_storage,
    )
    text_value = models.TextField(blank=True, default="")
    url = models.URLField(max_length=500, blank=True, default="")
    # Captured at submission time where the host makes one derivable, so the
    # museum degrades to a still image rather than an empty box when
    # somebody deletes their video in a year.
    thumbnail_url = models.URLField(max_length=500, blank=True, default="")
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["deliverable__order", "id"]

    def __str__(self):
        return f"{self.deliverable} for {self.submission_id}"


class UploadToken(models.Model):
    """Carried over from 2026 because it solves a real problem: the phone
    that photographs the bench at 3am is not the laptop that is signed in.
    The QR encodes a tokenised URL, so the upload binds to the right team
    and challenge without the phone authenticating."""

    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="upload_tokens")
    challenge = models.ForeignKey(Challenge, on_delete=models.CASCADE, related_name="upload_tokens")
    token = models.CharField(max_length=64, unique=True, default=new_token)
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["team", "challenge"], name="ct_upload_token_unique"),
        ]

    @property
    def is_valid(self):
        return timezone.now() <= self.expires_at


# ------------------------------------------------- judging, results, museum


class JudgeGrade(models.Model):
    """A human number for a creativity submission (Rule 8.2).

    More than one judge may grade the same submission, which is why this is
    a row rather than a field.
    """

    submission = models.ForeignKey(Submission, on_delete=models.CASCADE, related_name="grades")
    judge = models.ForeignKey(USER, on_delete=models.CASCADE, related_name="ct_grades")
    grade = models.PositiveSmallIntegerField(default=0)
    note = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
        constraints = [
            models.UniqueConstraint(fields=["submission", "judge"], name="ct_grade_unique"),
        ]

    def __str__(self):
        return f"{self.judge} graded {self.submission_id}: {self.grade}"


class Certificate(models.Model):
    PARTICIPATION, WINNER, RUNNER_UP = "participation", "winner", "runner_up"
    TYPES = [(PARTICIPATION, "Participation"), (WINNER, "Winner"), (RUNNER_UP, "Runner-up")]

    hackathon = models.ForeignKey(Hackathon, on_delete=models.CASCADE, related_name="certificates")
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="certificates")
    type = models.CharField(max_length=14, choices=TYPES, default=PARTICIPATION)
    cert_id = models.UUIDField(default=_uuid.uuid4, unique=True, editable=False)
    generated_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["hackathon", "team"], name="ct_certificate_unique"),
        ]


class MuseumPage(models.Model):
    """The permanent public page an event ends in (Rule 9.1).

    Most of it assembles itself from what the event already produced: the
    exhibition, the standings, the feedback. The human adds photos and a
    paragraph. Opening a blank page after a sleepless night is how a museum
    never gets published.
    """

    hackathon = models.OneToOneField(Hackathon, on_delete=models.CASCADE, related_name="museum_page")
    published = models.BooleanField(default=False)
    highlights = models.TextField(blank=True, default="")
    published_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Museum: {self.hackathon.slug}"


class MuseumPhoto(models.Model):
    """The museum is participatory, not curated-only (Rule 9.2).

    Once open, anyone signed in may add photos and anyone at all may
    download them: the people who were there have the good pictures, and
    the admin has twenty of the four hundred that exist. Which is also why
    `moderation_status` is here (Rule 9.3): a permanent public page anyone
    may post to is a permanent public page anyone may post anything to.
    """

    PENDING, APPROVED, REJECTED = "pending", "approved", "rejected"
    MODERATION = [(PENDING, "Pending"), (APPROVED, "Approved"), (REJECTED, "Rejected")]

    museum_page = models.ForeignKey(MuseumPage, on_delete=models.CASCADE, related_name="photos")
    image = models.ImageField(upload_to="crashtech/museum/", storage=media_storage)
    caption = models.CharField(max_length=200, blank=True, default="")
    # Null for the admin's own curated set.
    uploaded_by = models.ForeignKey(USER, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    moderation_status = models.CharField(max_length=8, choices=MODERATION, default=PENDING)
    order = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["order", "-created_at", "id"]


# ------------------------------------------------------------------ research


class Study(models.Model):
    """A research study, which deliberately **spans events** (Rule 10.1).

    Everything else in this file belongs to one hackathon. A study does
    not, because the research question is about events plural: how people
    behave in a timed hardware competition, compared across years.

    The thesis and the literature review live here rather than in a file
    in somebody's drive because a study spanning three events spans three
    years, and the reasoning behind the questions is the first thing lost
    in that time.
    """

    title = models.CharField(max_length=200)
    description = models.TextField(blank=True, default="")
    thesis = models.TextField(blank=True, default="")
    research_questions = models.TextField(blank=True, default="")
    literature_review = models.TextField(blank=True, default="")
    literature_updated_at = models.DateTimeField(null=True, blank=True)

    researchers = models.ManyToManyField(USER, blank=True, related_name="ct_studies")
    hackathons = models.ManyToManyField(Hackathon, blank=True, related_name="studies")

    consent_text = models.TextField(blank=True, default="")
    consent_version = models.CharField(max_length=40, default="v1")
    ethics_reference = models.CharField(max_length=160, blank=True, default="")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name_plural = "studies"

    def __str__(self):
        return self.title


class StudyReference(models.Model):
    """A source, as a row. A `TextField` full of pasted citations is the
    "JSON file as real data" mistake in prose form (building_an_app.md
    Rule 1)."""

    study = models.ForeignKey(Study, on_delete=models.CASCADE, related_name="references")
    citation = models.TextField()
    url = models.URLField(max_length=500, blank=True, default="")
    doi = models.CharField(max_length=120, blank=True, default="")
    year = models.PositiveSmallIntegerField(null=True, blank=True)
    # Why this one matters to the thesis, which is the part a bibliography
    # always loses.
    note = models.TextField(blank=True, default="")
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]


class Questionnaire(models.Model):
    """Attached to a milestone, so a question about the kit is asked when
    the kit arrives rather than six weeks later (Rule 10.2). This is the
    reason `Milestone` is a model at all."""

    study = models.ForeignKey(Study, on_delete=models.CASCADE, related_name="questionnaires")
    milestone_kind = models.CharField(max_length=12, choices=Milestone.KINDS)
    title = models.CharField(max_length=200)
    intro = models.TextField(blank=True, default="")
    is_open = models.BooleanField(default=True)

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return self.title


class Question(models.Model):
    TEXT, SCALE, SINGLE, MULTI, NUMBER = "text", "scale", "single_choice", "multi_choice", "number"
    KINDS = [
        (TEXT, "Free text"), (SCALE, "Scale"), (SINGLE, "Single choice"),
        (MULTI, "Multiple choice"), (NUMBER, "Number"),
    ]

    questionnaire = models.ForeignKey(Questionnaire, on_delete=models.CASCADE, related_name="questions")
    text = models.TextField()
    kind = models.CharField(max_length=14, choices=KINDS, default=TEXT)
    choices = models.JSONField(default=list, blank=True)
    required = models.BooleanField(default=False)
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]


class Response(models.Model):
    questionnaire = models.ForeignKey(Questionnaire, on_delete=models.CASCADE, related_name="responses")
    hackathon = models.ForeignKey(Hackathon, on_delete=models.CASCADE, related_name="responses")
    # Null when the study is anonymised.
    user = models.ForeignKey(USER, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    submitted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["submitted_at"]


class Answer(models.Model):
    response = models.ForeignKey(Response, on_delete=models.CASCADE, related_name="answers")
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name="answers")
    value = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["question__order", "id"]


class ResearchConsent(models.Model):
    """Per person, per study, per event, versioned and withdrawable
    (Rule 10.4).

    **The only thing in this entire model that cannot be added
    afterwards**, because data collected without it cannot be made usable
    retroactively. The 2026 platform had one consent flag, for publishing
    team photos; research consent is a different promise entirely: what is
    collected, what it is for, whether it is identifiable, and whether
    somebody can withdraw later and have their data excluded.

    `consent_version` exists so that changing the terms does not silently
    inherit agreement to the old ones.
    """

    study = models.ForeignKey(Study, on_delete=models.CASCADE, related_name="consents")
    user = models.ForeignKey(USER, on_delete=models.CASCADE, related_name="ct_consents")
    hackathon = models.ForeignKey(Hackathon, on_delete=models.CASCADE, related_name="consents")
    granted = models.BooleanField(default=False)
    consent_version = models.CharField(max_length=40, default="v1")
    granted_at = models.DateTimeField(null=True, blank=True)
    withdrawn_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["study", "user", "hackathon"], name="ct_consent_unique"),
        ]

    @property
    def is_active(self):
        return self.granted and self.withdrawn_at is None
