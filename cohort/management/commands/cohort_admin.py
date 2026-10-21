"""Avi's chat-side tools for the course site.

    manage.py cohort_admin tracks
    manage.py cohort_admin owner <track-slug> <email>
    manage.py cohort_admin admin <email> [--off]
    manage.py cohort_admin members
"""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone


class Command(BaseCommand):
    help = "List tracks and members, name a track's owner, mark a member as admin."

    def add_arguments(self, parser):
        parser.add_argument("action", choices=["tracks", "owner", "admin", "members"])
        parser.add_argument("rest", nargs="*")
        parser.add_argument("--off", action="store_true")

    def handle(self, *_, **options):
        action, args, off = options["action"], options["rest"], options["off"]
        from cohort.access import display_name_for
        from cohort.models import Member, Track

        User = get_user_model()

        def member_for(email):
            user = User.objects.filter(email__iexact=email).order_by("id").first()
            if user is None:
                raise CommandError(f"no account with the email {email}")
            member, _ = Member.objects.get_or_create(user=user, defaults={
                "display_name": display_name_for(user), "status": Member.APPROVED, "decided_at": timezone.now(),
            })
            return member

        if action == "tracks":
            for t in Track.objects.select_related("owner"):
                self.stdout.write(f"{t.slug:28} {t.name:30} owner: {t.owner.display_name if t.owner else '-'}")
        elif action == "members":
            for m in Member.objects.select_related("user"):
                self.stdout.write(f"{m.user.email:36} {m.display_name:24} {m.status}{' admin' if m.is_admin else ''}")
        elif action == "owner":
            if len(args) != 2:
                raise CommandError("owner <track-slug> <email>")
            track = Track.objects.filter(slug=args[0]).first()
            if track is None:
                raise CommandError(f"no track {args[0]}")
            track.owner = member_for(args[1])
            track.save(update_fields=["owner"])
            self.stdout.write(f"{track.name}: owner is now {track.owner.display_name}")
        elif action == "admin":
            if len(args) != 1:
                raise CommandError("admin <email> [--off]")
            member = member_for(args[0])
            member.is_admin = not off
            member.save(update_fields=["is_admin"])
            self.stdout.write(f"{member.display_name}: admin {'off' if off else 'on'}")
