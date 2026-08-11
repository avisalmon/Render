r"""Local helpers for re-running the /welcome/ chat as a fresh visitor.

The welcome chat only runs once per account, so trying it twice means starting
from a clean user.

    .\env\Scripts\python.exe scripts\reset_welcome_test_user.py
        Wipe the throwaway test*@local.test accounts so the same address can be
        registered again at /register/. That path always has a name (the form
        demands one), so it exercises the ONE-question flow.

    .\env\Scripts\python.exe scripts\reset_welcome_test_user.py --nameless
        Also create a user with no name at all, which is what a Google signup
        without a display name looks like. This is the only way to see stage 1,
        where the bot asks for the name and keeps asking. Prints the login.

    .\env\Scripts\python.exe scripts\reset_welcome_test_user.py foo@bar.com
        Wipe one specific address.
"""
import os
import sys

import django

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "mysite.settings")
django.setup()

from django.contrib.auth.models import User  # noqa: E402

from app.models import LearnerProfile  # noqa: E402

PREFIX = "test"
DOMAIN = "@local.test"
NAMELESS_USER = "testnameless"
NAMELESS_PASSWORD = "WelcomeTest123!"

args = [a for a in sys.argv[1:] if not a.startswith("--")]
nameless = "--nameless" in sys.argv

if args:
    qs = User.objects.filter(email__in=args)
else:
    qs = User.objects.filter(email__startswith=PREFIX, email__endswith=DOMAIN)

qs = qs.filter(is_superuser=False, is_staff=False)  # never touch a real account
found = list(qs.values_list("username", "email"))
for username, email in found:
    print("deleting", username, email)
qs.delete()
print(f"{len(found)} user(s) deleted" if found else "nothing to delete")

if nameless:
    User.objects.filter(username=NAMELESS_USER).delete()
    u = User.objects.create_user(
        NAMELESS_USER, email=f"{NAMELESS_USER}{DOMAIN}", password=NAMELESS_PASSWORD
    )
    u.first_name = ""          # no name anywhere - the bot has to ask for it
    u.save(update_fields=["first_name"])
    u.profile.display_name = ""
    u.profile.email_verified = True
    u.profile.save(update_fields=["display_name", "email_verified"])
    LearnerProfile.objects.get_or_create(user=u)
    print()
    print("nameless user ready - the bot will ask for a name:")
    print(f"  1. http://127.0.0.1:8000/login/   user: {NAMELESS_USER}   pass: {NAMELESS_PASSWORD}")
    print("  2. http://127.0.0.1:8000/welcome/")
