"""Security headers the framework does not set (security review, 2026-10-24).

A Content-Security-Policy that the whole site can live with today. The pages
carry inline scripts everywhere, so scripts are not restricted yet; what the
policy does restrict is what a planted script could do with the page: no
plugins, no rewriting of the page's base URL, forms post only to this site
(and to Google for sign-in), and the site is not framed by others. A
stricter script policy can follow once inline scripts move to files.
"""

CSP = (
    "object-src 'none'; "
    "base-uri 'self'; "
    "form-action 'self' https://accounts.google.com; "
    "frame-ancestors 'self'"
)


class SecurityHeadersMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        response.headers.setdefault("Content-Security-Policy", CSP)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        return response
