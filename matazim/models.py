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
