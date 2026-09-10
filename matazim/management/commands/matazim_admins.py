"""Grant and revoke מט״צים adminship.

REQ-M.68: adminship is seeded, never self-served. There is no screen that makes
someone an admin, because the first one could never have used it.

Runs on every deploy from `MATAZIM_ADMINS`, so the list of admins is an
environment variable rather than a code change: adding someone is a setting, not
a release.

    manage.py matazim_admins                       # who is an admin now
    manage.py matazim_admins --from-env            # what the deploy runs
    manage.py matazim_admins --grant a@b.com       # by hand
    manage.py matazim_admins --revoke a@b.com

An email that matches no account is reported and skipped. It is never created: a
typo must not conjure an account holding the highest role in the system.
"""

import os

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

from matazim.models import MemberProfile

ENV_VAR = "MATAZIM_ADMINS"


class Command(BaseCommand):
    help = "Grant, revoke or list מט״צים adminship (REQ-M.68)."

    def add_arguments(self, parser):
        parser.add_argument("--grant", nargs="*", default=[], metavar="EMAIL")
        parser.add_argument("--revoke", nargs="*", default=[], metavar="EMAIL")
        parser.add_argument(
            "--from-env",
            action="store_true",
            help=f"read the list from ${ENV_VAR} (comma separated)",
        )

    def handle(self, *args, **options):
        grant = list(options["grant"])
        revoke = list(options["revoke"])

        if options["from_env"]:
            raw = os.environ.get(ENV_VAR, "")
            grant += [part.strip() for part in raw.split(",") if part.strip()]
            if not raw:
                self.stdout.write(f"{ENV_VAR} is empty, nothing to grant")

        for email in grant:
            self._set(email, True)
        for email in revoke:
            self._set(email, False)

        if not grant and not revoke:
            self._list()

    def _set(self, email, value):
        user = User.objects.filter(email__iexact=email).first()
        if user is None:
            # Deliberately not created. A typo must not conjure an account
            # holding the highest role in the system.
            self.stdout.write(self.style.WARNING(f"no account for {email}, skipped"))
            return

        profile, _ = MemberProfile.objects.get_or_create(user=user)
        if profile.is_admin == value:
            self.stdout.write(f"{email} already {'an admin' if value else 'not an admin'}")
            return

        profile.is_admin = value
        profile.save(update_fields=["is_admin", "updated_at"])
        word = "granted to" if value else "revoked from"
        self.stdout.write(self.style.SUCCESS(f"adminship {word} {email}"))

    def _list(self):
        admins = MemberProfile.objects.filter(is_admin=True).select_related("user")
        if not admins:
            self.stdout.write("no מט״צים admins yet")
            return
        self.stdout.write("מט״צים admins:")
        for profile in admins:
            self.stdout.write(f"  {profile.user.email or profile.user.username}")
