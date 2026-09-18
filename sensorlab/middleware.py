"""The language a SensorLab request runs under.

This exists because of what SL-A2 found. The site is Hebrew-first —
`LANGUAGE_CODE = "he"`, plus `app.middleware.DefaultHebrewMiddleware`
forcing it — so Django's *own* strings (form labels, validation errors)
came out in Hebrew inside a SensorLab page whose `<html lang>` said `en`.
SensorLab's language is neither the site's setting nor the browser's guess:
it is the person's own choice, stored on their profile.

**Why middleware and not a decorator.** A decorator would have to be
remembered on every new view, and forgetting it fails silently — the page
renders, in the wrong language. Middleware cannot be forgotten. It is
registered once in the project's `MIDDLEWARE`, which is the same category
of unavoidable wiring as the URL include and the error handlers: it acts on
`/sensorlab/` only and changes nothing for any other app (Rule 2).
`ustrip.middleware.UstripErrorNotifier` is the existing precedent.

**Why `translation.override` and not `activate`.** `activate()` sets a
thread-local that the *next* request on that worker inherits. A person
reading SensorLab in English could flip babook's own pages out of Hebrew
for whoever that worker served next. `override` is a context manager and
restores what was there before — and there is a test for exactly that.
"""

from django.utils import translation

from .strings import DEFAULT_LANGUAGE, LANGUAGES

PREFIX = "/sensorlab/"
SESSION_KEY = "sensorlab_language"


def language_for(request):
    """Whose choice wins.

    A signed-in person's profile is the authority: it is the setting they
    chose, and it should follow them onto a new device rather than depend on
    a cookie. The session covers the visitor who has not signed in yet —
    without it the sign-in page itself could not be read in Hebrew, which
    would make the switch available only to people who already got in.
    """
    user = getattr(request, "user", None)
    if user is not None and user.is_authenticated:
        from .profiles import profile_for

        return profile_for(user).language
    chosen = (getattr(request, "session", {}) or {}).get(SESSION_KEY)
    return chosen if chosen in LANGUAGES else DEFAULT_LANGUAGE


class SensorLabLanguageMiddleware:
    """Runs SensorLab's requests in SensorLab's language, and only those."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not request.path.startswith(PREFIX):
            return self.get_response(request)

        language = language_for(request)
        request.sensorlab_language = language
        request.sensorlab_dir = "rtl" if language == "he" else "ltr"
        # What the switch in the header points at — computed here so no
        # template has to know there are exactly two languages.
        request.sensorlab_other_language = "en" if language == "he" else "he"

        with translation.override(language):
            response = self.get_response(request)

        # Say so out loud: a page that renders in Hebrew should not claim
        # otherwise to a screen reader, a translator, or a cache.
        response.headers.setdefault("Content-Language", language)
        return response
