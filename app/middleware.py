"""
Custom middleware for babook.
"""
from django.conf import settings


class DefaultHebrewMiddleware:
    """Force Hebrew as the default language for visitors who haven't set a preference.

    LocaleMiddleware normally picks up Accept-Language from the browser, which
    causes English-browser users to see LTR even though the site is Hebrew-first.
    This middleware injects the language cookie before LocaleMiddleware inspects the
    request, so first-time visitors always get Hebrew RTL. Subsequent visits respect
    whatever the user toggled via the language switcher.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        cookie_name = getattr(settings, "LANGUAGE_COOKIE_NAME", "django_language")
        no_pref = not request.COOKIES.get(cookie_name)
        if no_pref:
            # Inject Hebrew into the request cookies so LocaleMiddleware sees it
            request.COOKIES = {**request.COOKIES, cookie_name: "he"}

        response = self.get_response(request)

        if no_pref:
            response.set_cookie(
                cookie_name,
                "he",
                max_age=getattr(settings, "LANGUAGE_COOKIE_AGE", 365 * 24 * 3600),
                path=getattr(settings, "LANGUAGE_COOKIE_PATH", "/"),
                domain=getattr(settings, "LANGUAGE_COOKIE_DOMAIN", None),
                samesite="Lax",
            )
        return response
