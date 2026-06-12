"""Process pending AuthoringJobs (worker / fallback for hosts where the
background thread or web-host YouTube download is unavailable). REQ-4.3.6.

Usage:
    python manage.py run_authoring_jobs            # process all pending jobs once
    python manage.py run_authoring_jobs --id 5     # process a specific job
"""
from django.core.management.base import BaseCommand

from app.authoring.pipeline import run_job
from app.models import AuthoringJob


class Command(BaseCommand):
    help = "Process pending Authoring Studio jobs."

    def add_arguments(self, parser):
        parser.add_argument("--id", type=int, default=None, help="Process only this job id")

    def handle(self, *args, **options):
        if options["id"]:
            jobs = AuthoringJob.objects.filter(pk=options["id"])
        else:
            jobs = AuthoringJob.objects.filter(status="pending")
        if not jobs:
            self.stdout.write("No pending jobs.")
            return
        for job in jobs:
            self.stdout.write(f"Processing job #{job.pk}: {job.title} ...")
            run_job(job.pk)
            job.refresh_from_db()
            self.stdout.write(f"  -> {job.status} ({job.progress}%)")
