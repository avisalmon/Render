"""What מט״צים is entitled to know about a person.

The identity itself is not ours. Name, avatar, email and every הדרכה a person
has done live in babook's shared tables, and a name edited here changes there
too, because a person has one name. What is ours is the handful of facts that
only exist because מט״צים exists: did they find us through this door, have they
been told this is a prototype, and have they passed the entrance test.

Keeping those here rather than on babook's `UserProfile` is what lets RULE-3
stay true while still meeting "use the same profile model": the shared facts
stay shared, and only our own flags are ours. See docs/matazim/spec.md §4.
"""

from django.contrib.auth.models import User
from django.db import models


class MemberProfile(models.Model):
    """מט״צים's companion to babook's UserProfile. One row per person we meet."""

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="matazim_profile")

    # REQ-M.35 — did this person find us here, or are they a babook member who
    # wandered over? Without it the funnel cannot be read later.
    entered_via_matazim = models.BooleanField(default=False, verbose_name="נכנס דרך מט״צים")
    first_seen_at = models.DateTimeField(auto_now_add=True)

    # REQ-M.40 — the prototype disclaimer was put in front of them, and they
    # acknowledged it. Stored so we can say who was told and when.
    welcome_accepted_at = models.DateTimeField(
        null=True, blank=True, verbose_name="אישר את הודעת אב הטיפוס"
    )

    # Provisional (spec §4): a stored flag while the entrance test is a
    # placeholder, derived from EntranceAttempt once REQ-M.17 lands. Every
    # caller goes through has_passed_entrance_test() so that swap changes
    # nothing outside this file.
    entrance_test_passed_at = models.DateTimeField(
        null=True, blank=True, verbose_name="עבר את מבחן הכניסה"
    )

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "פרופיל מט״צים"
        verbose_name_plural = "פרופילי מט״צים"

    def __str__(self):
        return f"{self.user.email or self.user.username} · מט״צים"

    def has_passed_entrance_test(self):
        return self.entrance_test_passed_at is not None

    def has_accepted_welcome(self):
        return self.welcome_accepted_at is not None


class EntranceTarget(models.Model):
    """One object in the entrance-test bank.

    The geometry lives in files that a management command generated offline:
    an STL, a dimensioned drawing, and an answer key the web process never
    exposes. This row exists so a **person** can take an object out of
    circulation without anything being deleted (REQ-M.55). Litala and Avi decide
    what a 14-year-old should be asked to build; the generator only proposes.
    """

    target_id = models.CharField(max_length=16, unique=True, db_index=True)
    shape = models.CharField(max_length=40)
    title = models.CharField(max_length=120, blank=True, default="")
    brief = models.TextField(blank=True, default="")

    is_retired = models.BooleanField(default=False, verbose_name="הוצא משימוש")
    retired_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    retired_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["target_id"]
        verbose_name = "משימת מבחן כניסה"
        verbose_name_plural = "משימות מבחן כניסה"

    def __str__(self):
        return f"{self.target_id} · {self.title}"

    @property
    def drawing_url(self):
        return f"/static/matazim/targets/{self.target_id}.svg"

    @property
    def model_url(self):
        return f"/static/matazim/targets/{self.target_id}.stl"


class EntranceAttempt(models.Model):
    """One go at the entrance test.

    A retry is a new row rather than an edit, because the history is the point:
    someone who missed, read the feedback and came back has shown more of what
    this program selects for than someone who passed first time (REQ-M.53).
    """

    member = models.ForeignKey("MemberProfile", on_delete=models.CASCADE, related_name="attempts")
    target_id = models.CharField(max_length=16)
    number = models.PositiveIntegerField(default=1)

    model_file = models.FileField(upload_to="matazim_entrance/", blank=True, null=True)
    measured = models.JSONField(default=dict, blank=True)
    issues = models.JSONField(default=list, blank=True)
    passed = models.BooleanField(default=False)

    submitted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["number"]
        unique_together = [("member", "number")]
        verbose_name = "ניסיון מבחן כניסה"
        verbose_name_plural = "ניסיונות מבחן כניסה"

    def __str__(self):
        return f"{self.member.user.email} · ניסיון {self.number} · {self.target_id}"

    @property
    def is_open(self):
        """Waiting for an upload. There is at most one of these per member."""
        return self.submitted_at is None
