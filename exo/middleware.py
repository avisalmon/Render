"""The language an /exo/ request runs under.

Same shape and same reasoning as `sensorlab/middleware.py`, which is the
precedent on this site for a bilingual app inside a Hebrew-first project.

**Why middleware and not a decorator.** A decorator must be remembered on
every new view, and forgetting it fails *silently* — the page renders, in the
wrong language. Middleware cannot be forgotten. It acts on `/exo/` only and
changes nothing for any other app (building_an_app.md Rule 2).

**Why `translation.override` and not `activate`.** `activate()` sets a
thread-local the *next* request on that worker inherits, so one person reading
exo in English could flip babook's own pages out of Hebrew for whoever that
worker served next. `override` restores what was there before, and there is a
test for exactly that.

**Why this never creates a Membership.** Reading a language must not have a
side effect. Auto-creating a row here would manufacture "members" out of
anyone who merely loaded a public page — including people who never asked for
access — and quietly corrupt the very list Avi approves from.
"""

from django.utils import translation

from .strings import DEFAULT_LANGUAGE, LANGUAGES

PREFIX = "/exo/"
SESSION_KEY = "exo_language"


def language_for(request):
    """Whose choice wins: the person's saved choice, then the session, then
    Hebrew. Read-only — see the module docstring."""
    user = getattr(request, "user", None)
    if user is not None and getattr(user, "is_authenticated", False):
        membership = getattr(user, "exo_membership", None)
        if membership is not None and membership.language in LANGUAGES:
            return membership.language
    chosen = (getattr(request, "session", None) or {}).get(SESSION_KEY)
    return chosen if chosen in LANGUAGES else DEFAULT_LANGUAGE


class ExoLanguageMiddleware:
    """Runs exo's requests in exo's language, and only those."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not request.path.startswith(PREFIX):
            return self.get_response(request)

        language = language_for(request)
        request.exo_language = language
        request.exo_dir = "rtl" if language == "he" else "ltr"
        # What the switch in the header points at, computed here so no
        # template has to know there are exactly two languages.
        request.exo_other_language = "en" if language == "he" else "he"

        with translation.override(language):
            response = self.get_response(request)

        # Say so out loud: a page rendered in Hebrew should not claim otherwise
        # to a screen reader, a translator, or a cache.
        response.headers.setdefault("Content-Language", language)
        return response
