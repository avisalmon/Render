"""Move what is already exposed.

0006 changed where *new* uploads go. This moves the ones already written, which
is the half that actually closes spec §4.10 finding P2: every entrance-test
model uploaded before today is sitting in `MEDIA_ROOT/matazim_entrance/` under
the name the teenager's own file had, and `/media/` is served with no
authentication whatsoever.

Each file is moved to the private directory under a random name and the row is
repointed. The original is deleted afterwards, because leaving it is the entire
problem.

Deliberately forgiving. A missing file is not an error worth failing a deploy
over: the row keeps its old name, the serving view 404s on it, and nothing is
exposed either way. Better a deploy that lands than one that rolls back and
leaves the files public for another day.
"""

import uuid
from pathlib import Path

from django.conf import settings
from django.db import migrations


def move_files(apps, schema_editor):
    Attempt = apps.get_model("matazim", "EntranceAttempt")

    media = Path(settings.MEDIA_ROOT)
    private = Path(settings.MATAZIM_PRIVATE_DIR) / "entrance"
    moved = skipped = 0

    for attempt in Attempt.objects.exclude(model_file="").exclude(model_file=None):
        old_name = attempt.model_file.name or ""
        # Anything already under the new scheme was written by 0006 or later.
        if old_name.startswith("entrance/"):
            continue

        source = media / old_name
        if not source.is_file():
            skipped += 1
            continue

        private.mkdir(parents=True, exist_ok=True)
        new_name = f"entrance/{uuid.uuid4().hex}{source.suffix.lower()[:10]}"
        target = Path(settings.MATAZIM_PRIVATE_DIR) / new_name

        target.write_bytes(source.read_bytes())
        attempt.model_file.name = new_name
        attempt.save(update_fields=["model_file"])

        # Only now, once the row points at the copy. An interrupted migration
        # should leave a file reachable twice rather than not at all.
        source.unlink()
        moved += 1

    if moved or skipped:
        print(f"  matazim uploads: {moved} moved out of public media, {skipped} missing")


def unmove(apps, schema_editor):
    """Deliberately not reversible.

    Putting a minor's work back into a publicly served directory is not
    something a `migrate --backwards` should be able to do by accident.
    """
    raise RuntimeError("refusing to move minors' uploads back into the public media directory")


class Migration(migrations.Migration):
    dependencies = [("matazim", "0006_alter_entranceattempt_model_file")]
    operations = [migrations.RunPython(move_files, unmove)]
