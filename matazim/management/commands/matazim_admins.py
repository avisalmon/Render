"""Grant and revoke the מט״צים program-manager role.

REQ-M.68: the program-manager role is seeded, never self-served. There is no
screen that makes the first one, because they could never have used it.

Runs on every deploy from the environment, so the list is a setting rather than
a release.

**Two variable names are read, on purpose.** The role was renamed from "admin"
to "program manager" on 2026-09-11 (spec §4.3), and this command is what keeps
נעמי in her role in production: it runs on every deploy. Renaming the variable
and relying on somebody to update Render at exactly the right moment would mean
that, if they did not, the next deploy would silently stop granting the role and
nobody would notice until she could not open a screen. So `MATAZIM_PROGRAM_MANAGERS`
is preferred and `MATAZIM_ADMINS` still works. The old name is dropped only once
Render is confirmed updated.

    manage.py matazim_admins                       # who holds it now
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

ENV_VAR = "MATAZIM_PROGRAM_MANAGERS"
LEGACY_ENV_VAR = "MATAZIM_ADMINS"


def _emails_from_env():
    """The new variable if it is set, otherwise the old one.

    Deliberately not merged. Two half-filled lists would be a confusing state to
    debug, and the point of the fallback is continuity, not aggregation.
    """
    raw = os.environ.get(ENV_VAR, "").strip()
    if raw:
        return raw, ENV_VAR
    return os.environ.get(LEGACY_ENV_VAR, "").strip(), LEGACY_ENV_VAR


class Command(BaseCommand):
    help = "Grant, revoke or list the מט״צים program-manager role (REQ-M.68)."

    def add_arguments(self, parser):
        parser.add_argument("--grant", nargs="*", default=[], metavar="EMAIL")
        parser.add_argument("--revoke", nargs="*", default=[], metavar="EMAIL")
        parser.add_argument(
            "--from-env",
            action="store_true",
            help=f"read the list from ${ENV_VAR} or ${LEGACY_ENV_VAR} (comma separated)",
        )

    def handle(self, *args, **options):
        grant = list(options["grant"])
        revoke = list(options["revoke"])

        if options["from_env"]:
            raw, source = _emails_from_env()
            grant += [part.strip() for part in raw.split(",") if part.strip()]
            if not raw:
                self.stdout.write(
                    f"neither {ENV_VAR} nor {LEGACY_ENV_VAR} is set, nothing to grant"
                )

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
        if profile.is_program_manager == value:
            self.stdout.write(
                f"{email} already {'a program manager' if value else 'not a program manager'}"
            )
            return

        profile.is_program_manager = value
        profile.save(update_fields=["is_program_manager", "updated_at"])
        word = "granted to" if value else "revoked from"
        self.stdout.write(self.style.SUCCESS(f"program manager {word} {email}"))

    def _list(self):
        managers = MemberProfile.objects.filter(is_program_manager=True).select_related("user")
        if not managers:
            self.stdout.write("no מט״צים program managers yet")
            return
        self.stdout.write("מט״צים program managers:")
        for profile in managers:
            self.stdout.write(f"  {profile.user.email or profile.user.username}")
