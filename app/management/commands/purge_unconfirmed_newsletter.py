from django.core.management.base import BaseCommand
from django.utils import timezone

from app.models import NewsletterSubscriber


class Command(BaseCommand):
    help = "Purge unconfirmed newsletter subscribers older than 14 days."

    def handle(self, *args, **options):
        cutoff = timezone.now() - timezone.timedelta(days=14)
        deleted, _ = NewsletterSubscriber.objects.filter(
            confirmed_at__isnull=True,
            created_at__lt=cutoff,
        ).delete()
        self.stdout.write(f"Purged {deleted} unconfirmed newsletter subscribers")
