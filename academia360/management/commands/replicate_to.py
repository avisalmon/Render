"""Push this database's Academia360 rows and private files to another
instance of the app, through its API (spec 3; the day-one road from Avi's PC,
where the confidential reference lives, to production).

    manage.py replicate_to --base https://babook.co.il [--token T] [--force] [--files-only] [--rows-only]

Rows go as Django fixtures in chunks, in model order, so foreign keys always
arrive after what they point at. Files go one by one as raw bytes, by the
name the row already carries; one already in place is left alone. The audit,
AI and people-and-roles tables are never replicated (roles are granted on
the target, by the admin). The token comes from --token or
ACADEMIA360_AGENT_TOKEN in the environment.
"""

import json
import os
import urllib.error
import urllib.request

from django.apps import apps
from django.core import serializers
from django.core.management.base import BaseCommand, CommandError

SKIP = {"ChangeLog", "AgentRun", "AccessLog", "AiConversation", "AiMessage", "AiUsage", "Role", "CommitteeAttribute",
        "LeaderOf", "Invitation", "RoleRequest", "PublicProfile", "PublicComment", "Like", "CorrectionProposal"}
CHUNK = 150


class Command(BaseCommand):
    help = "Replicate Academia360's rows and private files to another instance through its API."

    def add_arguments(self, parser):
        parser.add_argument("--base", required=True)
        parser.add_argument("--token", default=os.environ.get("ACADEMIA360_AGENT_TOKEN", ""))
        parser.add_argument("--force", action="store_true")
        parser.add_argument("--rows-only", action="store_true")
        parser.add_argument("--files-only", action="store_true")
        parser.add_argument("--models", default="", help="comma-separated model names; only these rows travel (Epic P: the public-knowledge tables after a re-import, never the committee's work)")

    # The one place the network is touched; tests replace it.
    def send(self, method, url, body, content_type):
        req = urllib.request.Request(url, data=body, method=method)
        req.add_header("Content-Type", content_type)
        req.add_header("Accept", "application/json")
        req.add_header("Authorization", f"Bearer {self.token}")
        try:
            with urllib.request.urlopen(req, timeout=600) as resp:
                raw = resp.read().decode("utf-8")
                return resp.status, (json.loads(raw) if raw else {})
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode("utf-8", "replace")
            try:
                return exc.code, json.loads(raw)
            except json.JSONDecodeError:
                return exc.code, {"detail": raw[:300]}

    def handle(self, *args, **options):
        self.token = options["token"]
        if not self.token:
            raise CommandError("no token: pass --token or set ACADEMIA360_AGENT_TOKEN")
        base = options["base"].rstrip("/") + "/academia360/api/admin/replicate/"
        force = "?force=1" if options["force"] else ""
        if not options["files_only"]:
            models = [m for m in apps.get_app_config("academia360").get_models() if m.__name__ not in SKIP]
            wanted = {m.strip() for m in options["models"].split(",") if m.strip()}
            if wanted:
                unknown = wanted - {m.__name__ for m in models}
                if unknown:
                    raise CommandError(f"--models: unknown or never-replicated: {sorted(unknown)}")
                models = [m for m in models if m.__name__ in wanted]
            total = 0
            first = True
            for model in models:
                rows = list(model._default_manager.order_by("pk"))
                for i in range(0, len(rows), CHUNK):
                    data = serializers.serialize("json", rows[i:i + CHUNK])
                    suffix = force if first else (force + "&chunk=continue" if force else "?chunk=continue")
                    status, body = self.send("POST", base + suffix, data.encode("utf-8"), "application/json")
                    first = False
                    if status >= 300:
                        raise CommandError(f"{model.__name__}: {status} {body}")
                    total += body.get("saved", 0)
                self.stdout.write(f"{model.__name__:24} {len(rows):5}")
            self.stdout.write(f"rows sent: {total}")
        if not options["rows_only"]:
            sent = skipped = 0
            for key, model_name in (("submittedfile", "SubmittedFile"), ("responseletter", "ResponseLetter")):
                model = apps.get_model("academia360", model_name)
                for row in model._default_manager.exclude(file="").order_by("pk"):
                    storage = row.file.storage
                    if not storage.exists(row.file.name):
                        self.stdout.write(f"missing locally: {row.file.name}")
                        continue
                    with storage.open(row.file.name, "rb") as fh:
                        payload = fh.read()
                    status, body = self.send("PUT", f"{base}file/{key}/{row.pk}/{force}", payload,
                                             "application/octet-stream")
                    if status >= 300:
                        raise CommandError(f"{model_name} {row.pk}: {status} {body}")
                    if body.get("saved"):
                        sent += 1
                    else:
                        skipped += 1
            self.stdout.write(f"files sent: {sent}, already there: {skipped}")
