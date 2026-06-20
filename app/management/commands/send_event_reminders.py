"""Event reminder notifications (REQ-6.7.2).

Run hourly (cron / scheduler). Idempotent: each event carries reminded_24h /
reminded_1h flags so a member is reminded at most once per window. Notifies all
'going' RSVPs (and best-effort emails them).
"""
from datetime import timedelta

from django.conf import settings
from django.core.mail import send_mail
from django.core.management.base import BaseCommand
from django.utils import timezone


class Command(BaseCommand):
    help = "Notify 'going' attendees of events starting in ~24h and ~1h."

    def handle(self, *args, **opts):
        from app.community import notify
        from app.models import CommunityEvent
        now = timezone.now()
        sent = 0

        # 24h window: events starting in 23–25h, not yet reminded.
        for ev in CommunityEvent.objects.filter(
                reminded_24h=False, start_at__gte=now + timedelta(hours=23),
                start_at__lte=now + timedelta(hours=25)):
            sent += self._remind(ev, "מחר", notify, send_mail)
            ev.reminded_24h = True
            ev.save(update_fields=["reminded_24h"])

        # 1h window: events starting within the next ~1.5h, not yet reminded.
        for ev in CommunityEvent.objects.filter(
                reminded_1h=False, start_at__gte=now,
                start_at__lte=now + timedelta(minutes=90)):
            sent += self._remind(ev, "בקרוב", notify, send_mail)
            ev.reminded_1h = True
            ev.save(update_fields=["reminded_1h"])

        self.stdout.write(f"Sent {sent} event reminder(s).")

    def _remind(self, event, when_he, notify, send_mail):
        count = 0
        going = event.rsvps.filter(status="going").select_related("user")
        for r in going:
            notify(r.user, verb="event_reminder",
                   text=f"תזכורת: «{event.title}» מתחיל {when_he} ({event.start_at:%d/%m %H:%M})",
                   url=f"/community/events/{event.slug}/")
            if r.user.email:
                try:
                    send_mail(
                        f"תזכורת: {event.title}",
                        f"האירוע «{event.title}» מתחיל {when_he}.\n"
                        f"https://babook.co.il/community/events/{event.slug}/",
                        getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@babook.co.il"),
                        [r.user.email], fail_silently=True)
                except Exception:  # noqa: BLE001 - a reminder must never crash the batch
                    pass
            count += 1
        return count
