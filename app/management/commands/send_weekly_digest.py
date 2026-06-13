"""Weekly community digest (REQ-6.4.4).

Gated by DEC-46: the digest stays DORMANT until the community passes ~50 active
members — until then the live feed alone carries the pulse and a weekly email
would feel empty. Below the threshold this command sends nothing (and says so),
so it is safe to wire to a scheduler now and have it "switch on" automatically
once the community grows.
"""
from datetime import timedelta

from django.conf import settings
from django.core.mail import send_mail
from django.core.management.base import BaseCommand
from django.db.models import Count
from django.utils import timezone

ACTIVE_MEMBER_THRESHOLD = 50  # DEC-46


def active_member_count(since_days=30):
    """Distinct members who produced any community content recently."""
    from app.models import ForumPost, ForumThread, ShowcaseProject, Tip
    since = timezone.now() - timedelta(days=since_days)
    users = set()
    users |= set(Tip.objects.filter(created_at__gte=since).values_list("author_id", flat=True))
    users |= set(ForumThread.objects.filter(created_at__gte=since).values_list("author_id", flat=True))
    users |= set(ForumPost.objects.filter(created_at__gte=since).values_list("author_id", flat=True))
    users |= set(ShowcaseProject.objects.filter(
        published_at__gte=since).values_list("author_id", flat=True))
    users.discard(None)
    return len(users)


class Command(BaseCommand):
    help = "Send the weekly community digest to opted-in members (gated, DEC-46)."

    def add_arguments(self, parser):
        parser.add_argument("--force", action="store_true",
                            help="Bypass the active-member gate (testing/preview).")

    def handle(self, *args, **opts):
        from app.models import Tip, UserProfile

        count = active_member_count()
        if count < ACTIVE_MEMBER_THRESHOLD and not opts["force"]:
            self.stdout.write(
                f"Digest dormant (DEC-46): {count}/{ACTIVE_MEMBER_THRESHOLD} active "
                f"members. Nothing sent."
            )
            return

        week_ago = timezone.now() - timedelta(days=7)
        top_tip = (
            Tip.objects.filter(is_hidden=False, created_at__gte=week_ago)
            .annotate(n=Count("reactions")).order_by("-n", "-created_at").first()
        )
        recipients = (
            UserProfile.objects.filter(digest_opt_in=True)
            .select_related("user").exclude(user__email="")
        )
        sent = 0
        for profile in recipients:
            lines = ["שלום, הנה מה שקרה השבוע בקהילת babook:\n"]
            if top_tip:
                lines.append(f"💡 הטיפ של השבוע: {top_tip.body[:200]}")
            lines.append("\nלפיד המלא: https://babook.co.il/community/")
            try:
                send_mail(
                    "מה חדש בקהילת babook השבוע",
                    "\n".join(lines),
                    getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@babook.co.il"),
                    [profile.user.email],
                    fail_silently=True,
                )
                sent += 1
            except Exception:  # noqa: BLE001 — a digest must never crash the batch
                pass
        self.stdout.write(f"Digest sent to {sent} member(s).")
