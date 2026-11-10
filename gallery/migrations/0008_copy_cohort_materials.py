"""One time: everything on cohort's shared materials shelf, copied to the
gallery's shared shelf in the same order (Avi, 2026-11-10: "copy everything I
already put in cohort").

A deliberate, recorded exception to Rule 2 (an app never reads another app's
data): it reads cohort's rows and files once, here, and nothing in the running
gallery ever touches cohort. A migration runs once per database, so Avi's later
edits and deletions in the gallery are never undone by it. People's private
shelves in cohort are not copied: they are private.

A document's file is copied from cohort's private folder into the gallery's;
an item whose file is missing on this machine is copied without it and says
so in its line, rather than failing the deploy.
"""

import shutil
from pathlib import Path

from django.conf import settings
from django.db import migrations


def copy(apps, schema_editor):
    try:
        CohortMaterial = apps.get_model("cohort", "Material")
    except LookupError:
        return
    Material = apps.get_model("gallery", "Material")
    source_dir = Path(str(getattr(settings, "COHORT_PRIVATE_DIR", "")))
    target_dir = Path(str(settings.GALLERY_FILES_DIR))
    position = 0
    for old in CohortMaterial.objects.filter(owner__isnull=True).order_by("position", "created_at", "id"):
        position += 10
        tag = f"cohort:{old.pk}"
        if Material.objects.filter(source=tag).exists():
            continue
        name, line = "", old.line
        if old.file:
            src = source_dir / old.file.name
            if src.is_file():
                name = f"materials/{Path(old.file.name).name}"
                dest = target_dir / name
                dest.parent.mkdir(parents=True, exist_ok=True)
                if not dest.exists():
                    shutil.copy2(src, dest)
            else:
                line = (line + " (the file did not come over)")[:280]
        Material.objects.create(
            kind=old.kind, title=old.title, line=line, url=old.url, youtube_id=old.youtube_id or "",
            file=name, owner=None, position=position, source=tag,
        )


class Migration(migrations.Migration):
    dependencies = [
        ("gallery", "0007_materials"),
        ("cohort", "0006_material_shelves"),
    ]
    operations = [migrations.RunPython(copy, migrations.RunPython.noop)]
