"""
Capture a one-time screenshot cover for published showcase projects that have
a live site but no uploaded cover (REQ-6.3.17). Free screenshot service, no
OpenAI/token cost. Run once to backfill existing projects.
"""
from django.core.management.base import BaseCommand

from app.models import ShowcaseProject
from app.showcase_views import capture_site_cover


class Command(BaseCommand):
    help = "Snapshot live-site projects into stored covers (REQ-6.3.17)."

    def handle(self, *args, **opts):
        done = 0
        for p in ShowcaseProject.objects.filter(status="published", is_hidden=False):
            if p.cover or not p.site_url:
                continue
            self.stdout.write(f"capturing #{p.pk} {p.title} ({p.site_host}) ...")
            capture_site_cover(p.pk)
            p.refresh_from_db()
            if p.cover:
                done += 1
                self.stdout.write(self.style.SUCCESS(f"  saved {p.cover.name}"))
            else:
                self.stderr.write("  no cover (service slow/failed) — keeps live fallback")
        self.stdout.write(self.style.SUCCESS(f"done — {done} covers stored"))
