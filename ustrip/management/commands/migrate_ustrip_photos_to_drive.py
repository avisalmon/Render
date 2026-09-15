"""Move photos already sitting on Render's disk into Drive (Sprint 15).

`ItineraryPhoto` and `JournalPost` uploaded before this sprint have a local
file and nothing else. Every row uploaded after it goes straight to Drive
(see `ustrip/api.py::_attach_drive_photo`); this command is the one-time
bridge for whatever landed on disk in between Sprint 4 (deployed
2026-09-13) and this sprint.

**Idempotent and safe to re-run.** A row already carrying a `drive_file_id`
is skipped outright — it has nothing to do with this command any more. The
local file is only ever deleted *after* the Drive upload has come back with
an id, never before: a failed upload leaves the row exactly as it was, still
served from disk, and simply gets picked up again on the next run. Nothing
about photos already safely in Drive depends on the local file surviving,
so once every row is migrated the disk space is actually freed rather than
merely duplicated.

Run with `--dry-run` first to see the count without touching anything.
"""

from django.core.management.base import BaseCommand, CommandError

from app import drive

from ...models import ItineraryPhoto, JournalPost


class Command(BaseCommand):
    help = "One-time: upload existing local ustrip photos to Drive, freeing the local files."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="report what would move, change nothing")

    def handle(self, *args, **options):
        client = drive.from_env("ustrip")
        if client is None:
            raise CommandError(
                "Drive is not configured — set DRIVE_CLIENT_ID, DRIVE_CLIENT_SECRET, "
                "DRIVE_REFRESH_TOKEN and DRIVE_FOLDER_ID first."
            )

        dry_run = options["dry_run"]
        moved, failed = 0, 0

        for model, label in ((ItineraryPhoto, "item photo"), (JournalPost, "journal post")):
            # `photo` non-empty and no drive_file_id yet is exactly "still local,
            # not migrated" — a row with neither (a text-only journal post) is
            # correctly invisible to this query, there is nothing to move.
            pending = model.objects.exclude(photo="").filter(drive_file_id="")
            for row in pending:
                if dry_run:
                    self.stdout.write(f"would migrate {label} {row.pk}: {row.photo.name}")
                    continue
                if self._migrate_one(client, row, label):
                    moved += 1
                else:
                    failed += 1

        if dry_run:
            return

        self.stdout.write(self.style.SUCCESS(f"migrated {moved} photo(s) to Drive"))
        if failed:
            self.stdout.write(self.style.WARNING(f"{failed} photo(s) failed and are unchanged — re-run to retry"))

    def _migrate_one(self, client, row, label):
        try:
            with row.photo.open("rb") as fh:
                blob = fh.read()
        except OSError:
            self.stdout.write(self.style.WARNING(f"{label} {row.pk}: local file missing, skipped"))
            return False

        name = f"{row._meta.model_name}-{row.pk}-migrated.jpg"
        uploaded = client.upload_bytes(blob, name, mime="image/jpeg")
        if uploaded is None:
            self.stdout.write(self.style.WARNING(f"{label} {row.pk}: upload failed, left on disk"))
            return False

        old_file = row.photo
        row.drive_file_id = uploaded.file_id
        row.drive_url = uploaded.url
        row.content_type = "image/jpeg"
        row.photo = None
        row.save(update_fields=["drive_file_id", "drive_url", "content_type", "photo"])
        # Freed only now that the row no longer points at it and the Drive
        # copy is confirmed to exist — the order that makes a failure between
        # the two steps leave a duplicate rather than a loss.
        old_file.delete(save=False)
        self.stdout.write(f"{label} {row.pk}: moved to Drive ({uploaded.file_id})")
        return True
