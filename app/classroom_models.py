"""Chapter 9 - Teachers & Classes (Classrooms).

A member becomes a teacher, opens a class, and invites people by link, QR, or an
in-system invite. The teacher follows each student's progress and deliverables;
the class gets a shared space for discussions, teacher messages and a project
gallery. Privacy by role: progress and achievements are teacher-only; only
projects and discussions are shared with classmates.
"""

import secrets

from django.contrib.auth.models import User
from django.db import models


def gen_join_code():
    """A short, URL-safe, unguessable code that powers the join link and QR."""
    return secrets.token_urlsafe(8)


class TeacherClass(models.Model):
    """A class a teacher opens. Students join by link/QR or by invite."""

    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name="classes_owned")
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True, default="")
    join_code = models.CharField(max_length=24, unique=True, default=gen_join_code, db_index=True)
    is_open = models.BooleanField(default=True)  # accepting new members
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "כיתה"
        verbose_name_plural = "כיתות"

    def __str__(self):
        return f"{self.name} ({self.owner.username})"

    def active_memberships(self):
        return self.memberships.filter(status="active").select_related("student")

    @property
    def member_count(self):
        return self.memberships.filter(status="active").count()

    def is_member(self, user):
        if not user.is_authenticated:
            return False
        return self.memberships.filter(student=user, status="active").exists()


class ClassMembership(models.Model):
    STATUS = [
        ("invited", "Invited"),
        ("requested", "Requested"),
        ("active", "Active"),
        ("removed", "Removed"),
    ]
    klass = models.ForeignKey(TeacherClass, on_delete=models.CASCADE, related_name="memberships")
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name="class_memberships")
    status = models.CharField(max_length=10, choices=STATUS, default="active")
    # Opt-out model: a student's projects are shared with the class by default.
    share_projects = models.BooleanField(default=True)
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("klass", "student")]
        ordering = ["joined_at"]

    def __str__(self):
        return f"{self.student.username} in {self.klass.name} [{self.status}]"


class ClassInvite(models.Model):
    """In-system invite: a teacher invites an existing member to a class."""

    STATUS = [("pending", "Pending"), ("accepted", "Accepted"), ("declined", "Declined")]
    klass = models.ForeignKey(TeacherClass, on_delete=models.CASCADE, related_name="invites")
    inviter = models.ForeignKey(User, on_delete=models.CASCADE, related_name="class_invites_sent")
    invitee = models.ForeignKey(User, on_delete=models.CASCADE, related_name="class_invites_received")
    status = models.CharField(max_length=10, choices=STATUS, default="pending")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("klass", "invitee")]
        ordering = ["-created_at"]

    def __str__(self):
        return f"Invite {self.invitee.username} -> {self.klass.name} [{self.status}]"


class ClassJoinRequest(models.Model):
    """A student-initiated request to join a class, from the public directory.
    The teacher is notified in-system and by email, and approves or declines.
    One row per class+student (a re-request reopens the same row)."""

    STATUS = [("pending", "Pending"), ("approved", "Approved"), ("declined", "Declined")]
    klass = models.ForeignKey(TeacherClass, on_delete=models.CASCADE, related_name="join_requests")
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name="class_join_requests")
    status = models.CharField(max_length=10, choices=STATUS, default="pending")
    message = models.CharField(max_length=300, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    decided_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        unique_together = [("klass", "student")]
        ordering = ["-created_at"]

    def __str__(self):
        return f"Request {self.student.username} -> {self.klass.name} [{self.status}]"


class ClassMessage(models.Model):
    """A message in the classroom stream: a discussion post, or a teacher
    announcement when written by the class owner."""

    klass = models.ForeignKey(TeacherClass, on_delete=models.CASCADE, related_name="messages")
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name="class_messages")
    body = models.TextField()
    is_announcement = models.BooleanField(default=False)  # message from the teacher
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"Msg by {self.author.username} in {self.klass.name}"
