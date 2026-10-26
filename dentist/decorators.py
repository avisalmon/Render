"""`@signed_in`: like `login_required`, but a signed-out visitor is sent to
dentist's own sign-in screen, never to babook's (spec Rule 2.4).

CrashTech shipped the wrong door to production once and memz before it;
the fix is one decorator, used on every clinical view, and a test that
asserts on the redirect's destination, because a check for the substring
"/login/" passes on "/accounts/login/" too.
"""

from functools import wraps

from django.contrib.auth.decorators import login_required


def signed_in(view):
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        return login_required(view, login_url="dentist:login")(request, *args, **kwargs)

    return wrapped
