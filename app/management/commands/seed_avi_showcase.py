"""Seed Avi's real project sites into the community Showcase (דוכן השוויץ).

Idempotent - keyed on live_url, so it's safe to run on every deploy. Cover
images ship in the repo at data/showcase_seed/ and are copied into the cover
ImageField (MEDIA) the first time. Owner = the first superuser.
"""
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files import File
from django.core.management.base import BaseCommand
from django.utils import timezone

SITES = [
    ("avi-home.png", "האתר האישי של אבי סלמון",
     "דף הבית שלי - מנהיג טכנולוגי ומחנך", "https://avisalmon.github.io/homepage/"),
    ("stocks.png", "STOKS - סורק מניות",
     "כלי לסריקת מניות לפי השקעות ערך", "https://avisalmon.github.io/STOKS/"),
    ("ieee.png", "IEEE Milestones",
     "אבני דרך היסטוריות בטכנולוגיה", "https://avisalmon.github.io/homepage/ieee-milestones.html"),
    ("shakshuka.png", "אתר השקשוקה שלי",
     "כל מה שצריך לדעת על שקשוקה", "https://avisalmon.github.io/shakshuka/"),
]


class Command(BaseCommand):
    help = "Seed Avi's project sites into the Showcase (idempotent, keyed on live_url)."

    def handle(self, *args, **options):
        from app.models import ShowcaseProject

        author = get_user_model().objects.filter(is_superuser=True).order_by("id").first()
        if author is None:
            self.stderr.write("no superuser to own the projects - skipping")
            return

        src = Path(settings.BASE_DIR) / "data" / "showcase_seed"
        now = timezone.now()
        created = 0
        for fname, title, tagline, url in SITES:
            if ShowcaseProject.objects.filter(live_url=url).exists():
                self.stdout.write(f"  · exists: {title}")
                continue
            pr = ShowcaseProject(
                author=author, title=title, tagline=tagline, story=tagline,
                live_url=url, status="published", published_at=now)
            img = src / fname
            if img.exists():
                with open(img, "rb") as f:
                    pr.cover.save(fname, File(f), save=False)
            pr.save()
            created += 1
            self.stdout.write(self.style.SUCCESS(f"  + created: {title}"))
        self.stdout.write(self.style.SUCCESS(f"seed_avi_showcase done ({created} created)."))
