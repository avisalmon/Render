"""Seed the public bank, once (spec §6.1, §12.7; building_an_app.md "Data").

Public packs and their images come from `memz/seed_assets/<pack-slug>/`,
keyed by `MemeImage.seed_key` (the file's relative path). The rule is
check-before-create: a key that already has a row is left alone, whatever
an admin did to that row since (title edited, image retired to `rejected`),
and nothing is ever deleted. Deleting a row makes the next run recreate it;
to take an image out of the public bank, retire it in the admin instead.

Runs on every deploy from render.yaml (from SPR-Z.7), like every `seed_*`
command in this repo, and is safe to run any number of times.

The images shipped in SPR-Z.1 are generated placeholders (see
`memz/seed_assets/make_assets.py`); real content replaces them in SPR-Z.7
under Rule 6.1.1 (licensed or our own, never copyrighted meme templates).
"""

from pathlib import Path

from django.core.files import File
from django.core.management.base import BaseCommand

from memz.models import MemeImage, Pack, PackImage

ASSETS = Path(__file__).resolve().parents[2] / "seed_assets"

# (slug, name, description, order). A public pack is a category (data_model.md).
PACKS = [
    ("family", "משפחה", "רגעים מהבית: ארוחות, טיולים, ימי ראשון.", 0),
    ("animals", "חיות", "חתולים, כלבים ושאר חברים עם פרצוף.", 1),
    ("work", "עבודה", "פגישות, מיילים, וכל מה שביניהם.", 2),
    ("school", "בית ספר", "שיעורים, מבחנים והפסקות.", 3),
]

IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}


class Command(BaseCommand):
    help = "Seed memz's public packs and bank from memz/seed_assets/, one time only."

    def handle(self, *args, **options):
        verbosity = int(options.get("verbosity", 1))
        created_packs = created_images = linked = skipped = 0

        for slug, name, description, order in PACKS:
            pack, made = Pack.objects.get_or_create(
                owner=None, slug=slug,
                defaults={"name": name, "description": description, "is_public": True, "order": order},
            )
            created_packs += int(made)

            folder = ASSETS / slug
            files = sorted(p for p in folder.iterdir() if p.suffix.lower() in IMAGE_SUFFIXES) if folder.is_dir() else []
            for position, path in enumerate(files):
                key = f"{slug}/{path.name}"
                image = MemeImage.objects.filter(seed_key=key).first()
                if image is None:
                    image = MemeImage(
                        owner=None, visibility=MemeImage.PUBLIC, moderation_status=MemeImage.APPROVED,
                        moderation_note="seeded placeholder (SPR-Z.1); replaced by licensed content in SPR-Z.7",
                        seed_key=key, title=path.stem.replace("-", " ").replace("_", " "),
                    )
                    with path.open("rb") as fh:
                        image.file.save(path.name, File(fh), save=True)
                    created_images += 1
                else:
                    skipped += 1
                _link, made = PackImage.objects.get_or_create(pack=pack, image=image, defaults={"order": position})
                linked += int(made)

        if verbosity:
            self.stdout.write(
                f"seed_memz: packs +{created_packs}, images +{created_images} "
                f"(left alone {skipped}), links +{linked}"
            )
