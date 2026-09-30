"""Workshop groups: the link Avi sends to a room (spec §4.2).

Avi teaches this material. He needs to send one link to a course group, have
everyone in the room working within a minute, and see afterwards who came
through it and what they made.

**The link is a key, so it is built like one.** It approves whoever opens it,
on the spot, because thirty people cannot each wait for a tap. That makes it
the second privileged thing in this app, and it follows the same discipline as
the first (`approve_api.py`): the token is long and random rather than
guessable or sequential, it grants ordinary membership and never anything
above it, it can be killed by hand at any moment, and every use is recorded.

**It is also a clock.** Avi's own framing: the link is good for the day of the
workshop, and after that it should stop costing him tokens. So one window
governs two different doors:

- **Joining.** Outside the window the link is dead, and says so plainly rather
  than erroring.
- **Generating.** Outside the window a participant keeps everything they made
  and can read it, edit it, download it, publish it and browse the museum.
  Only the calls that reach a model stop. The line is exactly "does this spend
  money", which is one place in `ai._guard` rather than five in the views.

**Belonging accumulates.** Somebody who attends a second workshop joins the
second group and stays in the first. Their AI opens again because they now
have an open window, not because anything was reset, and work they make from
then on is stamped with the newer group. Stamping at creation is what keeps
"what came out of that workshop" a true answer a year later: a third workshop
must not quietly reattribute the first one's work.
"""

import secrets

from django.conf import settings
from django.db import models
from django.utils import timezone


class Cohort(models.Model):
    """One workshop, with a link and a window."""

    #: Long enough that guessing is not a strategy, and URL-safe so the link
    #: survives being pasted into a chat and a slide.
    TOKEN_BYTES = 24
    #: Avi's number: the link is good for the day of the workshop.
    WINDOW_HOURS = 24

    name = models.CharField(max_length=120)
    token = models.CharField(max_length=64, unique=True, db_index=True)

    #: When the workshop starts. Defaults to the moment the group is made, and
    #: can be set ahead for a link prepared the night before.
    starts_at = models.DateTimeField(default=timezone.now)
    window_hours = models.PositiveIntegerField(default=WINDOW_HOURS)

    #: Killed by hand. Separate from the clock so Avi can close a room early
    #: without waiting for a window to run out.
    is_closed = models.BooleanField(default=False)

    #: The one bound on a forwarded link (spec K7). This link breaks the BKM's
    #: "never create the principal" on purpose, because an invite that cannot
    #: make an account is not an invite, so the risk is bounded three ways
    #: instead: a short window, a kill switch, and this.
    max_joins = models.PositiveIntegerField(default=60)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="exo_cohorts_created",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-starts_at", "-id")

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.token:
            self.token = secrets.token_urlsafe(self.TOKEN_BYTES)
        return super().save(*args, **kwargs)

    # -- the window, computed rather than stored -------------------------- #

    @property
    def ends_at(self):
        return self.starts_at + timezone.timedelta(hours=self.window_hours)

    def is_open(self, now=None):
        """Is this workshop running right now?

        Computed from the clock every time it is asked, like the museum's
        timed visibility: nothing has to run on a schedule to close a window,
        so nothing can fail to run and leave one open.
        """
        if self.is_closed:
            return False
        now = now or timezone.now()
        return self.starts_at <= now < self.ends_at

    def closes_in(self, now=None):
        now = now or timezone.now()
        return max(timezone.timedelta(0), self.ends_at - now)

    def is_full(self):
        return self.members.count() >= self.max_joins

    def refusal(self, now=None):
        """Why this link will not let somebody in, or "" if it will.

        One function so the door and its tests agree, and so each refusal can
        carry its own plain sentence instead of a shared error page.
        """
        if self.is_closed:
            return "closed"
        now = now or timezone.now()
        if now < self.starts_at:
            return "not_started"
        if now >= self.ends_at:
            return "finished"
        if self.is_full():
            return "full"
        return ""

    def join_url(self, base=""):
        return f"{base}/exo/join/{self.token}/"


class CohortMember(models.Model):
    """One person's arrival through one link.

    A row per join rather than a field on the person, because "who came
    through this link" is the question Avi asked and it has to stay answerable
    after somebody attends a second workshop. Belonging accumulates; nothing
    here is ever moved or overwritten.
    """

    cohort = models.ForeignKey(
        Cohort, on_delete=models.CASCADE, related_name="members",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="exo_cohorts",
    )
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-joined_at", "-id")
        constraints = [
            models.UniqueConstraint(
                fields=["cohort", "user"], name="exo_one_join_per_cohort",
            )
        ]

    def __str__(self):
        return f"{self.user} in {self.cohort}"


def current_cohort(user):
    """The group new work should be stamped with: the most recent arrival.

    Most recent rather than most recently *open*, so a person who is between
    workshops still has their last one attached to anything they make. What
    governs the AI is a different question, asked in `has_open_window`.
    """
    if not getattr(user, "is_authenticated", False):
        return None
    joined = (CohortMember.objects.filter(user=user)
              .select_related("cohort").first())
    return joined.cohort if joined else None


def has_open_window(user, now=None):
    """Whether any workshop this person belongs to is running right now.

    Any, not the latest: attending a second workshop opens the AI again while
    that one runs, which is exactly what Avi described, and it falls out of
    this rule rather than needing one of its own.
    """
    if not getattr(user, "is_authenticated", False):
        return False
    now = now or timezone.now()
    for joined in CohortMember.objects.filter(user=user).select_related("cohort"):
        if joined.cohort.is_open(now=now):
            return True
    return False
