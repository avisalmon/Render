"""REQ-8.1.4 - nightly dashboard capture.

Collects all internal metrics, runs every cost adapter, and evaluates alert
thresholds into a snapshot. Idempotent and resilient: one weak collector or
adapter never aborts the rest. Schedule like the other cron jobs (e.g. Render
cron / scheduler), or run manually before a demo.
"""

from django.core.management.base import BaseCommand

from app.dashboard.capture import run_capture


class Command(BaseCommand):
    help = "Capture a dashboard snapshot (metrics + costs + alerts) for /admin-dashboard/."

    def add_arguments(self, parser):
        parser.add_argument(
            "--scope",
            default="all",
            choices=["all", "users_training", "engagement", "system", "costs"],
            help="Which section to capture (default: all).",
        )
        parser.add_argument(
            "--range-days",
            type=int,
            default=30,
            help="Window in days for range-sensitive metrics (default: 30).",
        )
        parser.add_argument("--no-costs", action="store_true", help="Skip running cost adapters.")
        parser.add_argument(
            "--no-alerts", action="store_true", help="Skip evaluating alert thresholds."
        )

    def handle(self, *args, **opts):
        result = run_capture(
            scope=opts["scope"],
            range_days=opts["range_days"],
            run_costs=not opts["no_costs"],
            run_alerts=not opts["no_alerts"],
        )
        snaps = ", ".join(result["snapshots"]) or "none"
        self.stdout.write(
            f"Captured [{snaps}]; "
            f"cost rows: {result['cost_rows']}; alerts raised: {result['alerts']}."
        )
