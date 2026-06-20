"""
Custom middleware for babook.
"""
from django.conf import settings
from django.shortcuts import redirect


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


class OnboardingMiddleware:
    """EPIC-5: first-touch intent capture + new-user onboarding routing.

    1. REQ-5.2.1 - records the anonymous visitor's first page request in the
       session (entry path/type/course, referrer, utm). Never overwritten.
    2. REQ-5.5.1 - a session flagged at signup ("onboarding_pending") routes
       the user's next page load to /welcome/, remembering where they were
       headed so onboarding can return them there. Only newly registered
       users are ever flagged; force_login / existing sessions are untouched.
    """

    _EXEMPT_PREFIXES = (
        "/welcome/", "/join/", "/logout/", "/login/", "/accounts/", "/admin/",
        "/static/", "/media/", "/api/", "/healthz", "/stripe/",
        "/verify-email/", "/resend-verification/", "/cookie-consent/",
    )

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        from .onboarding import (
            ONBOARDING_NEXT_KEY,
            ONBOARDING_PENDING_KEY,
            capture_first_touch,
        )

        capture_first_touch(request)

        if (
            request.method == "GET"
            and request.user.is_authenticated
            and request.session.get(ONBOARDING_PENDING_KEY)
            and not any(request.path.startswith(p) for p in self._EXEMPT_PREFIXES)
        ):
            profile = getattr(request.user, "learner_profile", None)
            if profile is not None and profile.needs_onboarding:
                if request.path != "/" and ONBOARDING_NEXT_KEY not in request.session:
                    request.session[ONBOARDING_NEXT_KEY] = request.get_full_path()
                return redirect("welcome")
            # Profile gone or already onboarded - stop intercepting.
            request.session.pop(ONBOARDING_PENDING_KEY, None)

        return self.get_response(request)
