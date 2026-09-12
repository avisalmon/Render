"""Read and close requests from the command line, which is where I work.

REQ-M.110 and REQ-M.111. The loop has a human at each end: נעמי writes, Avi
approves on the screen, and the sprint happens because Avi says so in
conversation. This command is the third side of that — how I read what is
approved when a sprint starts, and how I record what was actually built when it
ships.

It is deliberately a command and not a screen. A screen where I mark my own
work done is a screen that invites me to mark work done, and the record of what
was built should be written in the same act as building it.

    manage.py matazim_requests list
    manage.py matazim_requests list --status approved
    manage.py matazim_requests show 3
    manage.py matazim_requests done 3 --sprint SPR-M.26 --outcome "..." --mail
    manage.py matazim_requests assess 3
"""

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone


class Command(BaseCommand):
    help = "Read and close מט״צים improvement requests (§4.11)"

    def add_arguments(self, parser):
        sub = parser.add_subparsers(dest="action", required=True)

        listing = sub.add_parser("list", help="every request, newest first")
        listing.add_argument("--status", default="", help="new | approved | declined | done")

        show = sub.add_parser("show", help="one request in full")
        show.add_argument("id", type=int)

        done = sub.add_parser("done", help="record what was built for a request")
        done.add_argument("id", type=int)
        done.add_argument("--sprint", default="", help="e.g. SPR-M.26")
        done.add_argument("--outcome", required=True, help="what was actually built")
        done.add_argument(
            "--mail",
            action="store_true",
            help="send the summary to root and the requester (REQ-M.111)",
        )

        redo = sub.add_parser("assess", help="re-run the assessment for one request")
        redo.add_argument("id", type=int)

    def handle(self, *args, **options):
        from matazim.models import Request

        action = options["action"]

        if action == "list":
            rows = Request.objects.all().select_related("author")
            if options.get("status"):
                rows = rows.filter(status=options["status"])
            if not rows:
                self.stdout.write("no requests")
                return
            for row in rows:
                who = row.author.email or row.author.username
                head = row.body.strip().splitlines()[0][:72]
                self.stdout.write(
                    f"#{row.pk:<4} {row.status:<9} {row.created_at:%d.%m} {who:<26} {head}"
                )
            return

        if action == "show":
            row = self._get(Request, options["id"])
            self.stdout.write(f"#{row.pk} · {row.get_status_display()} · {row.get_kind_display()}")
            self.stdout.write(f"by {row.author.email} ({row.author_role}) {row.created_at:%d.%m.%Y %H:%M}")
            if row.from_screen:
                self.stdout.write(f"from {row.from_screen}")
            self.stdout.write("")
            self.stdout.write(row.body)
            if row.assessment:
                self.stdout.write("")
                self.stdout.write("-- assessment (machine-written) --")
                self.stdout.write(row.assessment)
            if row.outcome:
                self.stdout.write("")
                self.stdout.write(f"-- done{f' in {row.sprint}' if row.sprint else ''} --")
                self.stdout.write(row.outcome)
            return

        if action == "done":
            row = self._get(Request, options["id"])
            if row.status == Request.DECLINED:
                raise CommandError(
                    f"#{row.pk} was declined. Approve it on the queue screen first: "
                    "closing a request nobody approved would make the gate decorative."
                )
            row.status = Request.DONE
            row.sprint = options["sprint"] or row.sprint
            row.outcome = options["outcome"]
            row.done_at = timezone.now()
            row.save(update_fields=["status", "sprint", "outcome", "done_at"])
            self.stdout.write(self.style.SUCCESS(f"#{row.pk} recorded as done"))

            if options["mail"]:
                from matazim.request_mail import send_request_summary

                sent = send_request_summary(row)
                if sent:
                    self.stdout.write(self.style.SUCCESS(f"summary sent to {', '.join(sent)}"))
                else:
                    self.stdout.write(
                        self.style.WARNING("summary did not send (no address, or the cap)")
                    )
            return

        if action == "assess":
            from matazim.assess import assess

            row = self._get(Request, options["id"])
            text = assess(row)
            self.stdout.write(text or "no assessment (no API key, or the model was unreachable)")
            return

    def _get(self, model, pk):
        row = model.objects.filter(pk=pk).first()
        if row is None:
            raise CommandError(f"no request #{pk}")
        return row
