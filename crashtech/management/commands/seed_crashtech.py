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

from crashtech.models import (
    Challenge, ContentPage, Deliverable, Hackathon, KitItem, Milestone,
    ScheduleItem,
)

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


# One of each kind, because the difference between them is the product and
# an event with three completion challenges is the 2026 event the feedback
# complained about. They are seeded invisible, like every challenge: the
# demo event is at `kits`, and kickoff is what reveals them.
#
# Each carries its deliverables, so the demo shows a submit screen that
# actually names what is missing rather than an empty form.
CHALLENGES = [
    {
        "title": "Get the board talking",
        "kind": "completion",
        "points": 50,
        "brief": (
            "Bring the board up, read something real off it, and get a value "
            "out over serial. Any language, any toolchain, any amount of help "
            "from a model. It either works or it does not."
        ),
        "deliverables": [
            ("Source files", "file", "artifact", True, "A zip is fine."),
            ("Serial output, photographed", "image", "proof", True,
             "A phone photo of the terminal is fine."),
        ],
    },
    {
        "title": "Fastest 8-bit multiplier",
        "kind": "measured",
        "points": 0,
        "metric_name": "Fmax",
        "metric_unit": "MHz",
        "metric_direction": "higher_is_better",
        "rank_points": [60, 40, 25, 15, 10],
        "brief": (
            "Synthesise an 8x8 multiplier and report the Fmax your timing "
            "report gives you. Pipelining is allowed and so is everything "
            "else. Report the real number: the top few get looked at."
        ),
        "deliverables": [
            ("Timing report", "image", "proof", True,
             "The screenshot showing the number you reported."),
            ("HDL sources", "file", "artifact", True, ""),
            ("Demo video", "video", "proof", False,
             "Sixty seconds, pointed at the bench. A link, on any host."),
        ],
    },
    {
        "title": "Most elegant thing on the bench",
        "kind": "creativity",
        "points": 40,
        "max_grade": 10,
        "criteria": (
            "Does it do something nobody asked for, and does it do it well? "
            "We are looking for the thing you would show somebody, not the "
            "thing that scored."
        ),
        "brief": (
            "Anything you built that the other challenges do not cover. There "
            "is no number to report on this one: judges look at it after the "
            "event, so you will see no points until then."
        ),
        "deliverables": [
            ("Demo video", "video", "proof", True,
             "A link, on any host. Nothing is uploaded here."),
            ("What it is", "text", "artifact", True,
             "A paragraph. What it does and why you built it."),
        ],
    },
]


class Command(BaseCommand):
    help = "Create one clearly-labelled demo CrashTech event, if it is not already there."

    def handle(self, *args, **options):
        existing = Hackathon.objects.filter(slug=SLUG).first()
        if existing is not None:
            # The event is already there, so the event is left alone. What
            # this does do is add a part that did not exist when it was
            # first seeded, and only if it is still missing.
            #
            # That is the same shape as seed_blog: add what is absent,
            # never touch what is present. The demo event was first seeded
            # in C.1 with no challenges at all, because C.4 had not been
            # written yet, and without them the demo stops at the first
            # interesting step: going live reveals nothing.
            added = self._add_missing_challenges(existing)
            if added:
                self.stdout.write(
                    f"seed_crashtech: demo event already exists; added "
                    f"{added} missing challenges, sealed"
                )
            else:
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

        self._add_missing_challenges(event)

        ScheduleItem.objects.create(
            hackathon=event, title="Kickoff briefing", order=0,
            starts_at=event.starts_at,
            ends_at=event.starts_at + timezone.timedelta(hours=1),
            location="Technion, Electrical Engineering",
            description="What the challenges are worth, and where the judges sit.",
        )

        self.stdout.write(
            f"seed_crashtech: created the demo event at /crashtech/e/{SLUG}/ "
            f"({event.milestones.count()} milestones, {event.kit_items.count()} kit items, "
            f"{event.challenges.count()} challenges, all still sealed)"
        )


    def _add_missing_challenges(self, event):
        """Add any seeded challenge this event does not already have.

        Matched on title, so an event that has them keeps exactly what it
        has, including anything a tech lead has since edited. Returns how
        many were added.

        Seeded `visible=False` whatever the event's status, like every
        challenge everywhere: kickoff is the only thing that reveals one
        (Rule 7.1), and a seed that published a challenge into a live
        event would be the worst possible bug in this product.
        """
        added = 0
        for order, spec in enumerate(CHALLENGES):
            fields = dict(spec)
            deliverables = fields.pop("deliverables")
            if event.challenges.filter(title=fields["title"]).exists():
                continue
            challenge = Challenge.objects.create(
                hackathon=event, order=order, visible=False, **fields,
            )
            for position, (label, kind, purpose, required, help_text) in enumerate(deliverables):
                Deliverable.objects.create(
                    challenge=challenge, label=label, kind=kind, purpose=purpose,
                    required=required, help_text=help_text, order=position,
                )
            added += 1
        return added
