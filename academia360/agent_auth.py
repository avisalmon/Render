"""The agent's door (spec chapter 3; building_an_app.md "giving an agent a
key, without giving it the house").

One token, `ACADEMIA360_AGENT_TOKEN`, presented as `Authorization: Bearer
<token>` or `X-A360-Token`. It authenticates the request **as the admin
account inside this app only**: `request.user` becomes the site account
named by `ACADEMIA360_AGENT_USER` (Avi's), `request.a360_agent` is set so
every write is logged as the agent's, and nothing outside /academia360/ ever
sees this class, because only this app's viewsets list it.

- Unset token: closed. An empty header never equals an empty setting.
- Constant-time compare.
- Cannot create accounts, cannot change passwords or staff flags: the
  viewsets simply have no such routes; roles go through one narrow endpoint
  (api.RoleGrantView) that grants and revokes for accounts that already exist.
"""

from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils.crypto import constant_time_compare
from rest_framework import authentication, exceptions

HEADER = "X-A360-Token"


def presented_token(request):
    header = request.headers.get("Authorization", "")
    if header.startswith("Bearer "):
        return header[7:].strip()
    return request.headers.get(HEADER, "").strip()


def token_matches(request):
    expected = getattr(settings, "ACADEMIA360_AGENT_TOKEN", "") or ""
    presented = presented_token(request)
    if not expected or not presented:
        return False
    return constant_time_compare(presented, expected)


def agent_user():
    """The account the agent acts as: the one named in settings, else the
    first superuser. None when neither exists, which closes the door."""
    User = get_user_model()
    name = getattr(settings, "ACADEMIA360_AGENT_USER", "") or ""
    if name:
        user = User.objects.filter(username=name).first() or User.objects.filter(email__iexact=name).first()
        if user is not None:
            return user
    return User.objects.filter(is_superuser=True, is_active=True).order_by("pk").first()


class AgentTokenAuthentication(authentication.BaseAuthentication):
    def authenticate(self, request):
        if not presented_token(request):
            return None  # not for us; the session may still authenticate
        if not token_matches(request):
            raise exceptions.AuthenticationFailed("bad token")
        user = agent_user()
        if user is None:
            raise exceptions.AuthenticationFailed("no account for the agent to act as")
        request.a360_agent = True
        return (user, "agent-token")

    def authenticate_header(self, request):
        return "Bearer"
