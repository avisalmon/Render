"""Avi's finished BKMs as of 2026-10-26, put on the wall once (REQ-B.21).

A migration, not a seed, so a card Avi later removes never comes back on a
deploy. Pictures are attached by `seed_bkm` from bkm/seed_assets/.
"""

from django.db import migrations

FIRST = [
    ("full-stack", "FullStackBKM",
     "Build a real, safe, full-stack website (Django on Render) with Claude as your guide and mentor.",
     "https://github.com/avisalmon/FullStackBKM", "https://avisalmon.github.io/FullStackBKM/"),
    ("single-button-kit", "SingleButtonKitBKM",
     "Build the Single Button ESP32 kit, then program it with an AI guide.",
     "https://github.com/avisalmon/SingleButtonKitBKM", "https://avisalmon.github.io/SingleButtonKitBKM/"),
    ("de10-lite", "De10LiteBKM",
     "The Terasic DE10-Lite FPGA with an AI beside you: install, a Verilog course in nand2tetris order, and verified examples.",
     "https://github.com/avisalmon/De10LiteBKM", "https://avisalmon.github.io/De10LiteBKM/"),
]


def add(apps, schema_editor):
    Bkm = apps.get_model("bkm", "Bkm")
    for i, (slug, name, tagline, repo, page) in enumerate(FIRST):
        Bkm.objects.get_or_create(slug=slug, defaults={
            "name": name, "tagline": tagline, "repo_url": repo, "page_url": page, "position": (i + 1) * 10,
        })


class Migration(migrations.Migration):
    dependencies = [("bkm", "0001_initial")]
    operations = [migrations.RunPython(add, migrations.RunPython.noop)]
