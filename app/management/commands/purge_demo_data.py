"""Purge demo/test data, leaving a clean production site with only:
  - superuser (admin) accounts
  - course content (Course / Video / CourseMaterial / LessonQuiz)
  - showcase projects owned by a superuser (Avi's real portfolio)
  - operational/config data (dashboard snapshots, cost records, alerts, newsletter)

Everything else (non-admin users and all their data, CrashTech demo, community
events, forum, tips, channels, course interactions, certificates, corporate
leads, community reputation/notifications) is deleted.

Dry-run by default. Pass --yes to actually delete. Wrapped in a transaction.
"""
from django.apps import apps
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction


def _qs(model_name, **filters):
    model = apps.get_model("app", model_name)
    qs = model.objects.all()
    return qs.filter(**filters) if filters else qs


class Command(BaseCommand):
    help = "Purge demo/test data (keeps superusers, course content, admin showcase)."

    def add_arguments(self, parser):
        parser.add_argument("--yes", action="store_true",
                            help="Actually delete. Without it, only reports counts (dry-run).")

    def _plan(self):
        """List of (label, queryset) to delete, children-ish first. Cascades cover
        the rest. Missing models are skipped (returns None)."""
        User = get_user_model()
        spec = [
            ("CrashTech hackathons (+teams/challenges/submissions)", "Hackathon", {}),
            ("Event series", "EventSeries", {}),
            ("Community events (+RSVPs/photos)", "CommunityEvent", {}),
            ("Forum threads (+posts/votes)", "ForumThread", {}),
            ("Tips", "Tip", {}),
            ("Community channels (+messages)", "Channel", {}),
            ("Enrollments", "Enrollment", {}),
            ("Lesson progress", "UserVideoProgress", {}),
            ("Lesson reflections", "LessonReflection", {}),
            ("Certificates", "CourseCertificate", {}),
            ("Project submissions (image)", "CourseProjectSubmission", {}),
            ("Lesson model submissions", "LessonModelSubmission", {}),
            ("Notifications", "Notification", {}),
            ("Direct messages", "DirectMessage", {}),
            ("Content reports", "ContentReport", {}),
            ("Moderation logs", "ModerationLog", {}),
            ("Follows", "Follow", {}),
            ("Community reputation", "CommunityReputation", {}),
            ("Reputation events", "ReputationEvent", {}),
            ("Badge awards", "BadgeAward", {}),
            ("Corporate leads", "CorporateLead", {}),
        ]
        plan = []
        for label, model_name, filters in spec:
            try:
                plan.append((label, _qs(model_name, **filters)))
            except LookupError:
                continue
        # Showcase projects NOT owned by a superuser (admin portfolio is kept).
        try:
            plan.append((
                "Showcase projects (non-admin)",
                _qs("ShowcaseProject").exclude(author__is_superuser=True),
            ))
        except LookupError:
            pass
        # Finally non-admin users (cascades profiles, chat, seats, notes, etc.).
        plan.append(("Non-admin users", User.objects.filter(is_superuser=False)))
        return plan

    def handle(self, *args, **opts):
        User = get_user_model()
        plan = self._plan()

        self.stdout.write("=== purge plan (counts to delete) ===")
        for label, qs in plan:
            self.stdout.write(f"  {label}: {qs.count()}")
        self.stdout.write(
            f"=== keeping: superusers={User.objects.filter(is_superuser=True).count()}, "
            f"courses={_qs('Course').count()}, "
            f"admin showcase={_qs('ShowcaseProject').filter(author__is_superuser=True).count()} ==="
        )

        if not opts["yes"]:
            self.stdout.write(self.style.WARNING("DRY RUN - nothing deleted. Re-run with --yes."))
            return

        with transaction.atomic():
            for label, qs in plan:
                deleted, _ = qs.delete()
                self.stdout.write(self.style.SUCCESS(f"deleted {label}: {deleted}"))

        self.stdout.write(self.style.SUCCESS(
            f"DONE. Remaining users={User.objects.count()} "
            f"(superusers={User.objects.filter(is_superuser=True).count()}), "
            f"courses={_qs('Course').count()}."
        ))
