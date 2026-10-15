"""Shared by the matazim suites that need a learner who is attached to a leader.

REQ-M.191 and REQ-M.192 (Lital, 2026-10-15, through Avi): the site opens only for a
learner who has passed the test and joined a leader. Suites written before that,
when a person with no leader could use the whole site, make their people through
this so the people in them are the ones the site is now open to.
"""

from django.contrib.auth.models import User
from django.utils import timezone


def attach(user, leader=None):
    """Make `user` a student of a leader (a shared host one if none is given)."""
    from matazim.models import Institution, Leader, Student

    if leader is None:
        host = Leader.objects.filter(user__email="host-leader@example.com").first()
        if host is None:
            institution = Institution.objects.order_by("created_at").first() or Institution.objects.create(
                name="רשת עתיד")
            host_user = User.objects.create_user(
                username="host-leader@example.com", email="host-leader@example.com",
                password="host-pass-0000")
            host = Leader.objects.create(user=host_user, institution=institution,
                                         approved_at=timezone.now())
        leader = host
    Student.objects.get_or_create(user=user, defaults={"leader": leader, "status": Student.IN_TRAINING})
    return user
