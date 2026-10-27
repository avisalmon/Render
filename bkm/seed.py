"""The BKMs Avi has said are complete, and their pictures (REQ-B.21).

The rows are put on the wall once, by migrations (0002 onward), so a card
Avi removed never comes back. A picture is attached by `seed_bkm` only to a
BKM that has none, from the file committed in `bkm/seed_assets/<slug>.jpg`;
a picture Avi changed is never replaced.
"""

from pathlib import Path

from django.core.files import File

ASSETS = Path(__file__).resolve().parent / "seed_assets"

RESERVED = {"api", "login", "logout", "signup", "projects", "new"}


def attach_pictures(log=print):
    from .models import Bkm

    for bkm in Bkm.objects.all():
        if bkm.picture:
            try:
                if bkm.picture.storage.exists(bkm.picture.name):
                    continue
            except Exception:  # pragma: no cover - a storage that cannot say
                continue
        source = ASSETS / f"{bkm.slug}.jpg"
        if not source.exists():
            continue
        with source.open("rb") as fh:
            bkm.picture.save(f"{bkm.slug}.jpg", File(fh), save=True)
        log(f"bkm: picture for {bkm.slug}")
