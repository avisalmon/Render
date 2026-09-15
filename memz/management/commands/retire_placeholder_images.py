"""SPR-Z.7, Rule 6.1.1: retire the SPR-Z.1 placeholder bank images now that
real (AI-illustrated) content exists to replace them.

The seed itself never deletes or retires a row (`seed_memz`'s own rule:
check-before-create, nothing removed) — Rule 6.1.1 is explicit that this
needs "a dedicated migration or admin action" instead, which is this
command. It never touches the file or the database row itself, only the
moderation status: a `rejected` image is excluded from every public list
and every deal (`MemeImage.is_dealable`), which is the same mechanism the
site already uses for a genuinely rejected upload, so no new "retired"
state had to be invented. Nothing is deleted, so this is trivially safe
to run more than once, and reversible by hand in the admin if a
placeholder is ever wanted back before Rule 6.1.1's real content
actually lands in a pack.

    .\\env\\Scripts\\python.exe manage.py retire_placeholder_images
"""

from django.core.management.base import BaseCommand

from memz.models import MemeImage


class Command(BaseCommand):
    help = "Retire SPR-Z.1's placeholder bank images (spec Rule 6.1.1), one time."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        candidates = MemeImage.objects.filter(
            seed_key__contains="/placeholder-",
        ).exclude(moderation_status=MemeImage.REJECTED)
        count = candidates.count()
        if options["dry_run"]:
            self.stdout.write(f"retire_placeholder_images --dry-run: would retire {count}")
            return
        updated = candidates.update(
            moderation_status=MemeImage.REJECTED,
            moderation_note="retired: replaced by real content (SPR-Z.7, spec Rule 6.1.1)",
        )
        self.stdout.write(f"retire_placeholder_images: retired {updated}")
