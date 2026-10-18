"""The language, direction and theme a /books/ request runs under.

Same shape as exo/middleware.py and sensorlab/middleware.py, the precedent
on this site for a bilingual app inside a Hebrew-first project. Acts on
/books/ only (Rule 2). `translation.override`, never `activate`, so one
person reading Books in English cannot flip another app's page for whoever
that worker serves next.

Whose choice wins: the person's Profile, then the session (a visitor who
switched before signing in), then the browser's Accept-Language, then
Hebrew. The theme follows the same ladder, ending at light (spec BK1 §1.1b).
"""

from django.utils import translation

from .strings import DEFAULT_LANGUAGE, LANGUAGES

PREFIX = "/books/"
LANG_SESSION_KEY = "books_language"
THEME_SESSION_KEY = "books_theme"
THEMES = ("light", "dark", "system")
PALETTES = ("lamplit", "warm", "bright", "den")
SHELF_VIEWS = ("lamp", "bookcase", "living")


def _profile(request):
    user = getattr(request, "user", None)
    if user is not None and getattr(user, "is_authenticated", False):
        return getattr(user, "books_profile", None)
    return None


def language_for(request):
    profile = _profile(request)
    if profile is not None and profile.language in LANGUAGES:
        return profile.language
    session = getattr(request, "session", None)
    chosen = session.get(LANG_SESSION_KEY) if session is not None else None
    if chosen in LANGUAGES:
        return chosen
    header = request.META.get("HTTP_ACCEPT_LANGUAGE", "")
    for part in header.split(","):
        code = part.split(";")[0].strip().lower()[:2]
        if code in LANGUAGES:
            return code
    return DEFAULT_LANGUAGE


def appearance_for(request):
    """(theme, palette, shelf_view): the Profile's, else the session's theme,
    else the defaults Avi chose: light, lamp-lit, the lamp shelf."""
    profile = _profile(request)
    theme = getattr(profile, "theme", None)
    palette = getattr(profile, "palette", None)
    shelf_view = getattr(profile, "shelf_view", None)
    session = getattr(request, "session", None)
    if theme not in THEMES:
        theme = session.get(THEME_SESSION_KEY) if session is not None else None
    if theme not in THEMES:
        theme = "light"
    if palette not in PALETTES:
        palette = "lamplit"
    if shelf_view not in SHELF_VIEWS:
        shelf_view = "lamp"
    return theme, palette, shelf_view


class BooksMiddleware:
    """Runs Books' requests in Books' language and appearance, and only those."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not request.path.startswith(PREFIX):
            return self.get_response(request)

        language = language_for(request)
        request.books_lang = language
        request.books_dir = "rtl" if language == "he" else "ltr"
        request.books_other_lang = "en" if language == "he" else "he"
        request.books_theme, request.books_palette, request.books_shelf_view = appearance_for(request)
        # The browser chrome colour, from the token table in spec BK1 §1.1c.
        request.books_theme_color = "#120F0C" if request.books_theme == "dark" or request.books_palette == "den" else "#EFE6D6"

        with translation.override(language):
            response = self.get_response(request)
        response.headers.setdefault("Content-Language", language)
        return response
