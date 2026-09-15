"""Rate limits on the abusable, no-login surfaces (spec Rule 12.3.3.7).
Keyed by IP for anonymous callers (DRF's `AnonRateThrottle` default) so a
guest with no account cannot be told apart from a rate-limit's point of
view, and by user otherwise.

`get_rate()` reads `api_settings.DEFAULT_THROTTLE_RATES` fresh on every
call rather than relying on DRF's own `THROTTLE_RATES` class attribute,
which is bound once at import time and does not pick up a rate changed
later via Django's `setting_changed` signal (which is how a test overrides
it, and how a future admin-tunable rate would work too)."""

from rest_framework.settings import api_settings
from rest_framework.throttling import AnonRateThrottle, SimpleRateThrottle, UserRateThrottle


class _LiveRateMixin:
    def get_rate(self):
        return api_settings.DEFAULT_THROTTLE_RATES.get(self.scope)


class MemeCreateAnonThrottle(_LiveRateMixin, AnonRateThrottle):
    scope = "memz_meme_create_anon"


class MemeCreateUserThrottle(_LiveRateMixin, UserRateThrottle):
    scope = "memz_meme_create_user"


class ReportThrottle(_LiveRateMixin, AnonRateThrottle):
    scope = "memz_report"


class _IPRateThrottle(_LiveRateMixin, SimpleRateThrottle):
    """Keyed by IP regardless of login (spec Rule 12.3.3.7 asks for
    session creation and join attempts limited by IP specifically — DRF's
    own `AnonRateThrottle` would exempt a logged-in host entirely, which
    is not what "by IP" means here)."""

    def get_cache_key(self, request, view):
        return self.cache_format % {"scope": self.scope, "ident": self.get_ident(request)}


class SessionCreateThrottle(_IPRateThrottle):
    scope = "memz_session_create"


class JoinAttemptThrottle(_IPRateThrottle):
    scope = "memz_join_attempt"
