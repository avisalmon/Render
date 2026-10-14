"""Seed one clearly-labelled demo event, once (building_an_app.md, "Data").

**This is a one-time import, not a sync.** It checks before it creates and
never touches a row that already exists. That rule is here because of a
real incident on ustrip: a seed wired into `render.yaml` ran on every
deploy and wholesale deleted and recreated rows from a static file, which
would have silently destroyed a real person's edits the moment the app let
anybody change that table.

So: if the demo event is already there, this command changes nothing and
says so. Everything it writes is marked `DEMO` in the name, so it is
obvious what it is and trivial to delete.
"""

from django.core.management.base import BaseCommand
from django.utils import timezone

from crashtech.models import ContentPage, Hackathon, KitItem, Milestone, ScheduleItem

SLUG = "demo-vlsi"

MILESTONES = [
    ("publication", "Registration opens", -21, "Applications open. Tell your friends."),
    ("hardware", "Kit pickup day", -14, "Collect your board in person. One kit per team."),
    ("kickoff", "Kickoff", 0, "Every challenge opens at once. The clock starts."),
    ("close", "Submissions close", 1, "Judging begins. Judges do nothing until now."),
    ("museum", "Results and museum", 8, "Published permanently, and open to everyone."),
]

KIT = [
    ("Intel DE10-Lite", "MAX 10 FPGA board, 50 MHz, VGA and Arduino headers.", 30, True),
    ("ESP32-WROOM-32", "WiFi controller, programmed over USB with PlatformIO.", 30, True),
    ("SSD1306 OLED", "128x64 I2C display.", 30, False),
    ("Jumper wires and breadboard", "Bring them back if you like, nobody is counting.", 30, False),
]

PAGES = [
    ("about", "About this event", """CrashTech is a hardware hackathon. You get a kit, two weeks to
practise with it, and then twenty-four hours against a set of challenges
nobody has seen before.

There are no tutorials during the event and no live support. Use the
internet, use AI, use whatever you like. The challenges that reward you
most are the ones where neither you alone nor a model alone gets there."""),
    ("rules", "The rules", """**Teams.** Up to the size the organisers set for this event. Everybody on
a team can do everything: submit, upload, collect the kit. There is no
captain.

**Scoring.** You report your own results and the points land immediately.
We trust you. The scores that decide the winners are checked afterwards,
and you upload your source as part of every submission, which is what
makes trusting you reasonable.

**Creativity challenges** are judged by people, after the event. You will
see no points on them until then, and that is not a bug.

**Demo videos** are links. Host the video wherever you like and paste the
link. Nothing is uploaded here."""),
]


class Command(BaseCommand):
    help = "Create one clearly-labelled demo CrashTech event, if it is not already there."

    def handle(self, *args, **options):
        if Hackathon.objects.filter(slug=SLUG).exists():
            self.stdout.write("seed_crashtech: demo event already exists, left alone")
            return

        now = timezone.now()
        event = Hackathon.objects.create(
            name="DEMO - CrashTech VLSI",
            slug=SLUG,
            tagline="Twenty-four hours, one kit, and whatever you can make it do.",
            status=Hackathon.KITS,
            starts_at=now + timezone.timedelta(days=14),
            ends_at=now + timezone.timedelta(days=15),
            submission_deadline=now + timezone.timedelta(days=15),
            team_size_max=2,
            kits_per_team=1,
            repo_url="https://github.com/avisalmon/TechCrash2026",
        )

        for order, (kind, title, offset, blurb) in enumerate(MILESTONES):
            Milestone.objects.create(
                hackathon=event, kind=kind, title=title, blurb=blurb, order=order,
                occurs_at=event.starts_at + timezone.timedelta(days=offset),
            )

        for order, (name, description, qty, returnable) in enumerate(KIT):
            KitItem.objects.create(
                hackathon=event, name=name, description=description,
                quantity_total=qty, is_returnable=returnable, order=order,
            )

        for order, (slug, title, body) in enumerate(PAGES):
            ContentPage.objects.create(
                hackathon=event, slug=slug, title=title, body=body,
                published=True, order=order,
            )

        ScheduleItem.objects.create(
            hackathon=event, title="Kickoff briefing", order=0,
            starts_at=event.starts_at,
            ends_at=event.starts_at + timezone.timedelta(hours=1),
            location="Technion, Electrical Engineering",
            description="What the challenges are worth, and where the judges sit.",
        )

        self.stdout.write(
            f"seed_crashtech: created the demo event at /crashtech/e/{SLUG}/ "
            f"({event.milestones.count()} milestones, {event.kit_items.count()} kit items)"
        )
