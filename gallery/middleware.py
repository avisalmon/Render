"""The language a /gallery/ request runs under (REQ-G.6).

Same shape as `exo/middleware.py`, for the same reasons: middleware cannot be
forgotten on a new view, it acts on /gallery/ only, and `translation.override`
(not `activate`) so one English reader cannot flip the next request on the same
worker. Reading a language never creates a Person.
"""

from django.utils import translation

from .strings import DEFAULT_LANGUAGE, LANGUAGES

PREFIX = "/gallery/"
COOKIE = "gallery_lang"


def language_for(request):
    """The person's saved choice, then the cookie, then Hebrew."""
    user = getattr(request, "user", None)
    if user is not None and getattr(user, "is_authenticated", False):
        person = getattr(user, "gallery_person", None)
        if person is not None and person.language in LANGUAGES:
            return person.language
    chosen = request.COOKIES.get(COOKIE)
    return chosen if chosen in LANGUAGES else DEFAULT_LANGUAGE


class GalleryLanguageMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not request.path.startswith(PREFIX):
            return self.get_response(request)
        try:
            language = language_for(request)
        except Exception:  # a missing row reads as "no choice", never a crash
            language = DEFAULT_LANGUAGE
        request.gallery_language = language
        request.gallery_dir = "rtl" if language == "he" else "ltr"
        request.gallery_other_language = "en" if language == "he" else "he"
        with translation.override(language):
            response = self.get_response(request)
        response.headers.setdefault("Content-Language", language)
        return response
