"""`@signed_in`, which is `login_required` that knows where it lives.

Django's own `login_required` sends people to the project-wide
`LOGIN_URL`, which on this site is babook's allauth page. That is a seal
break (Rule 2.2.2): a visitor halfway through a CrashTech flow lands on
another product's branded sign-in, and the whole point of this app having
its own front door is that they never find out babook exists.

It shipped to production exactly once, on C.2, because every permission
test used `force_login` and therefore never walked the signed-out path.
memz made the same mistake once before.

So: one decorator, used everywhere, rather than remembering to pass
`login_url=` at thirty call sites. The one you forget is the one somebody
finds.
"""

from functools import wraps

from django.contrib.auth.decorators import login_required


def signed_in(view):
    """Require a signed-in user, and send them to **CrashTech's** login."""

    @wraps(view)
    def wrapped(request, *args, **kwargs):
        return login_required(view, login_url="crashtech:login")(request, *args, **kwargs)

    return wrapped
