"""Tell someone when ustrip breaks (spec §0a.2 reasoning, added 2026-09-14).

The trip is fifteen days with nobody watching a log. An unhandled error under
/ustrip/ on day six at Niagara currently renders the 500 page (good) and then
vanishes into Render's log (bad) — the family is stuck and Avi finds out when
someone texts him. This mails him instead, so a crash on the road is something
he can act on rather than something he learns about afterwards.

Deliberately narrow, the same way everything else here is:

- It only acts on `/ustrip/` paths. Middleware is project-wide, so it checks
  the path and does nothing for babook or מט״צים — their errors are their own
  concern, and this must not become a second, half-built error channel for the
  whole site.
- It re-raises nothing and swallows everything: a failure to send the warning
  must never turn one error into two, or replace ustrip's 500 page with a
  mail-server stack trace.
- It throttles by error signature, so a crashloop sends one message every
  THROTTLE_MINUTES, not one per request. (The throttle is per worker process,
  since there is no shared cache; a crashloop across N workers can therefore
  send up to N in a window. N is small and the alternative — a shared cache
  just for this — is not worth it.)
- The mail carries the path, method, the signed-in username, and a short
  traceback tail. Not the POST body: a journal caption or a photo has no place
  in an error email, and a password never should.
"""

import logging
import traceback

from django.conf import settings
from django.core.cache import cache
from django.core.mail import send_mail

log = logging.getLogger("ustrip.errors")

PREFIX = "/ustrip/"
THROTTLE_MINUTES = 30


def _recipient():
    """Only `USTRIP_ERROR_NOTIFY`, deliberately not a fallback chain.

    `DEFAULT_FROM_EMAIL` has a non-blank hardcoded default in this project
    ("noreply@babook.co.il") — it is a *sender* address, always present, not
    a signal that someone configured a recipient. Falling back to it (or to
    `CONTACT_NOTIFY_EMAIL`, which itself defaults to `DEFAULT_FROM_EMAIL`)
    would mean this notifier is never actually off: it would fire in every
    environment, including a laptop running the test suite, straight to an
    address nobody reads. One explicit setting, same as `USTRIP_ADMIN_TOKEN` —
    unset means off, not "guess at something reasonable."
    """
    return getattr(settings, "USTRIP_ERROR_NOTIFY", "")


class UstripErrorNotifier:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_exception(self, request, exception):
        # Return None always: this observes, it never changes how the error is
        # handled. Django still runs its own 500 path and renders ustrip/500.html.
        try:
            if not request.path.startswith(PREFIX):
                return None
            self._notify(request, exception)
        except Exception:  # noqa: BLE001 - the notifier must never add an error
            log.exception("ustrip error-notifier failed (original error still handled)")
        return None

    def _notify(self, request, exception):
        recipient = _recipient()
        if not recipient:
            return

        tb = traceback.extract_tb(exception.__traceback__)
        last = tb[-1] if tb else None
        # Signature: the type plus where it was raised. The message is left out
        # so "no such row 41" and "no such row 88" throttle as one error.
        signature = f"{type(exception).__name__}:{last.filename if last else '?'}:{last.lineno if last else 0}"
        throttle_key = f"ustrip-err:{signature}"
        if cache.get(throttle_key):
            return
        cache.set(throttle_key, True, THROTTLE_MINUTES * 60)

        who = request.user.get_username() if getattr(request.user, "is_authenticated", False) else "(anonymous)"
        tail = "".join(traceback.format_exception(type(exception), exception, exception.__traceback__))[-1800:]
        body = (
            f"ustrip hit an error a family member would have seen.\n\n"
            f"  where:  {request.method} {request.path}\n"
            f"  who:    {who}\n"
            f"  error:  {type(exception).__name__}: {exception}\n\n"
            f"Only the first of these per error is sent every {THROTTLE_MINUTES} minutes.\n\n"
            f"--- traceback (tail) ---\n{tail}"
        )
        send_mail(
            subject=f"[ustrip] {type(exception).__name__} on {request.path}",
            message=body,
            from_email=getattr(settings, "DEFAULT_FROM_EMAIL", None),
            recipient_list=[recipient],
            fail_silently=True,
        )
        log.warning("ustrip error mailed to %s: %s", recipient, signature)
