"""Look for traffic that came from the house's test suite rather than the house.

Disclosed by the home system on 2026-09-05. `RelayService._loop` initialised its
poll timers to `0.0` and compared against `time.monotonic()`, so the first
command poll fired on construction rather than ten seconds later. Every windowed
test in their suite built a relay from the real environment, which meant a test
run could collect a genuine command from our queue, execute it against its own
empty temporary database, and ack it `done`. Registered kinds include `arm`,
`disarm`, `acknowledge`, `snapshot`, `resync` and `delete_incident`.

    python manage.py security_leak_report

Read-only. It deletes nothing and changes nothing.

WHAT IT LOOKS FOR

1. `Cam A` / `Cam B` / `Cam C` - fixture camera names that exist nowhere in the
   real inventory, so anything here naming them is test traffic and dates the
   leak. They reported that no *event* was ever relayed from a test, since
   `relay_event` is called only from paths that do not run windowed; this checks
   that rather than taking it on trust.

2. `/state` overwritten by a fixture. One row, overwritten in place, and the
   banner is read from it, so a test could have replaced the phone's view of the
   house with its own.

3. Commands acked `done` whose effect never arrived. This is the one with a
   lasting mark. On `failed` we release the row; on `done` we deliberately do
   NOT, because `done` means the house is about to call `/deletions` and only
   that actually removes anything. A phantom `done` therefore leaves a row
   pending forever - visible on the phone as an incident stuck mid-delete.

   Note what could not happen: the phantom ack could not delete anything. "A
   request is not a deletion" meant the blast radius of a spoofed `done` was a
   stuck row rather than lost data.
"""

import re

from django.core.management.base import BaseCommand

from app.security_models import SecurityCommand, SecurityEvent, SecurityState, SecurityViewLog

FIXTURE_CAMERA = re.compile(r"\bCam\s+[ABC]\b", re.IGNORECASE)


class Command(BaseCommand):
    help = "Report traffic that looks like it came from the house's test suite."

    def handle(self, *args, **options):
        found = False

        # 1. fixture camera names, in events
        events = [e for e in SecurityEvent.objects.values_list(
            "event_id", "camera") if FIXTURE_CAMERA.search(e[1] or "")]
        self.stdout.write(f"events on a fixture camera : {len(events)}")
        for event_id, camera in events[:10]:
            found = True
            self.stdout.write(self.style.WARNING(f"   {event_id}  {camera}"))

        # 2. the state row
        state = SecurityState.current()
        if state:
            blob = f"{state.notes}"
            suspect = bool(FIXTURE_CAMERA.search(blob))
            self.stdout.write(
                f"state received             : {state.received_at:%Y-%m-%d %H:%M} "
                f"({state.cameras_online}/{state.cameras_total} cameras)")
            if suspect:
                found = True
                self.stdout.write(self.style.WARNING(
                    f"   notes mention a fixture camera: {state.notes[:120]}"))
        else:
            self.stdout.write("state received             : never")

        # 3. commands acked done whose effect never arrived
        phantom = []
        for command in SecurityCommand.objects.filter(ack_status="done"):
            if command.kind != "delete_incident":
                continue
            ids = (command.params or {}).get("event_ids") or []
            still_here = SecurityEvent.objects.filter(
                event_id__in=ids, delete_requested_at__isnull=False)
            if still_here.exists():
                phantom.append((command, still_here.count()))

        self.stdout.write(f"delete_incident acked done : "
                          f"{SecurityCommand.objects.filter(kind='delete_incident', ack_status='done').count()}")
        self.stdout.write(f"  of those, still pending  : {len(phantom)}")
        for command, count in phantom[:10]:
            found = True
            self.stdout.write(self.style.WARNING(
                f"   cmd {command.pk} acked done {command.acked_at:%Y-%m-%d %H:%M}, "
                f"{count} row(s) still marked pending"))

        stuck = SecurityEvent.objects.filter(
            delete_requested_at__isnull=False).count()
        self.stdout.write(f"rows stuck mid-delete      : {stuck}")

        # Context, so a reader can tell a leak from a quiet week.
        self.stdout.write(f"total events               : {SecurityEvent.objects.count()}")
        self.stdout.write(f"page views logged          : {SecurityViewLog.objects.count()}")

        if found:
            self.stdout.write(self.style.WARNING(
                "\nSomething here looks like test traffic. Nothing was changed."))
        else:
            self.stdout.write(self.style.SUCCESS(
                "\nNo fixture signature found."))
