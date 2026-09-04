"""Empty the /home event log, because the house is empty and cannot say which rows.

Written for the clear-out of 2026-09-04. The owner cleared the whole event log
in the desktop app; the house's `clear_events()` ran a raw `DELETE FROM events`
and never notified its delete listeners, so `/deletions` was never sent and
babook kept every row. The house then had nothing to send: relay_api.md §5.5
takes explicit `event_ids`, and theirs died with the rows.

    python manage.py purge_security_events              # report only
    python manage.py purge_security_events --apply      # do it

**Report only by default.** This removes everything rather than a selection,
which is exactly when a dry run earns its keep.

WHY THIS IS ALLOWED TO EXIST AT ALL, given REQ-11.1.3 says babook never decides
to delete anything. It still does not decide. The house asked, in writing, and
the owner confirmed. This is the manual form of that request, and both sides
agreed manual is the right amount of friction for a one-off. The guarded
`{"all": true}` declaration is the built form, and is a separate change.

THE ORDER MATTERS. The high-water mark is raised from the rows *before* they go.
`event_id` is the natural key, and a rebuilt house that restarts its counter at
1 would silently upsert onto historical rows rather than create new ones. The
house guards that with a floor derived from the Drive record filenames - and the
owner is emptying Drive, so this mark becomes the independent second copy. Purge
the rows without capturing it first and the number is gone with them.

Snapshot files are deleted too. They live on the same 1 GB disk as the site's
own database, so leaving thousands of orphaned JPEGs behind would be a slow leak
with nothing left pointing at it.
"""

from django.core.management.base import BaseCommand
from django.db.models import Max

from app.security_api import delete_snapshot_file
from app.security_models import SecurityCommand, SecurityEvent, SecurityHighWater


class Command(BaseCommand):
    help = "Delete every /home security event. Report-only unless --apply."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true",
                            help="actually delete; without it nothing changes")
        parser.add_argument("--keep-commands", action="store_true",
                            help="leave queued/acked commands in place")

    def handle(self, *args, **options):
        apply = options["apply"]
        total = SecurityEvent.objects.count()
        with_snap = SecurityEvent.objects.exclude(snapshot_path="").count()
        highest = SecurityEvent.objects.aggregate(m=Max("event_id"))["m"] or 0
        mark_before = SecurityHighWater.current()

        self.stdout.write(f"events            : {total}")
        self.stdout.write(f"with a snapshot   : {with_snap}")
        self.stdout.write(f"highest event_id  : {highest}")
        self.stdout.write(f"high-water mark   : {mark_before}")

        if not total:
            self.stdout.write(self.style.SUCCESS("nothing to purge"))
            return

        # Raise the mark FIRST, and from the rows themselves, so the id floor
        # outlives them. A mark that is already higher is left alone: it only
        # ever rises, or it would reintroduce the id reuse it exists to prevent.
        if apply:
            SecurityHighWater.note([highest, mark_before])
            self.stdout.write(f"high-water raised : {SecurityHighWater.current()}")
        else:
            self.stdout.write(
                f"would raise mark  : {max(highest, mark_before)}")

        if not apply:
            self.stdout.write(self.style.WARNING(
                "\nreport only. re-run with --apply to delete."))
            return

        removed_files = 0
        for path in (SecurityEvent.objects
                     .exclude(snapshot_path="")
                     .values_list("snapshot_path", flat=True)
                     .iterator()):
            delete_snapshot_file(path)
            removed_files += 1

        deleted = SecurityEvent.objects.all().delete()[0]

        commands = 0
        if not options["keep_commands"]:
            # Anything queued for the house refers to events that no longer
            # exist at either end. A `delete_incident` for a purged row would
            # be collected and fail, which is noise, not safety.
            commands = SecurityCommand.objects.filter(acked_at__isnull=True).delete()[0]

        self.stdout.write(self.style.SUCCESS(
            f"\ndeleted {deleted} events, {removed_files} snapshot files, "
            f"{commands} unacked commands"))
        self.stdout.write(
            f"high-water mark retained: {SecurityHighWater.current()} "
            "(the house can read this back after its own floor is gone)")
