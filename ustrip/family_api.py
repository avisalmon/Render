"""Managing who is in the family, over the wire (spec §3).

Why this exists: granting access was the one job that always stopped dead at
"Avi, open /admin/auth/user/ on your phone and tick a box." Everything else
about ustrip can be done from a chat; this could not, and four people needed
adding four days before the trip.

**What it deliberately cannot do.** This is not an admin key for babook. A
leaked token here must not be a skeleton key to a site that holds other
people's accounts and payment records, so the blast radius is fenced in by
the code, not by good intentions:

  - It only ever touches the ``family`` group. The group name is not a
    parameter — no caller can name a different one.
  - It never creates accounts. A person who has not signed up cannot be
    granted anything; the endpoint says so and stops. That keeps this from
    being a way to manufacture users.
  - It never grants ``is_staff`` or ``is_superuser``, and never edits a
    password, an email or any other field on the user.
  - It never deletes a user. Removing someone takes away ustrip access and
    nothing else.

So the worst a stolen token can do is add or remove someone on a private
family trip planner. That is a real annoyance and not a breach of anything
else on the site — which is the whole reason for scoping it this tightly
rather than building the general "admin API" that would have been quicker.

Auth is the convention already used by ``app/security_api.py`` and the backup
trigger: a shared secret from an environment variable, compared in constant
time, never in the repo. A logged-in superuser is also allowed, so the same
endpoint is usable from DRF's browsable API without a token at all.

Every grant and revoke is logged with who did it and how, because "who let
this person in" is a question that should have an answer.
"""

import logging

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.db.models import Q
from django.utils.crypto import constant_time_compare
from rest_framework.permissions import BasePermission
from rest_framework.response import Response
from rest_framework.views import APIView

from .access import FAMILY_GROUP
from .serializers import UserSummarySerializer

log = logging.getLogger(__name__)


class HasFamilyAdminToken(BasePermission):
    """A shared secret, or a superuser session.

    `==` on a secret leaks its length and prefix through timing, hence
    `constant_time_compare` — the same reason `app/security_api.py` spells it
    out. A missing token and a wrong token give the same answer, with no hint
    as to which.
    """

    message = "A valid family-admin token or a superuser session is required."

    def has_permission(self, request, view):
        user = request.user
        if user.is_authenticated and user.is_superuser:
            return True
        expected = getattr(settings, "USTRIP_ADMIN_TOKEN", "")
        if not expected:
            return False          # unset means closed, never open
        header = request.headers.get("Authorization", "")
        presented = header[7:] if header.startswith("Bearer ") else request.headers.get("X-Ustrip-Token", "")
        return constant_time_compare(presented, expected)


def _find_user(handle):
    """By username or email, case-insensitively. Returns None if nobody matches."""
    handle = (handle or "").strip()
    if not handle:
        return None
    User = get_user_model()
    return User.objects.filter(Q(username__iexact=handle) | Q(email__iexact=handle)).first()


def _actor(request):
    if request.user.is_authenticated:
        return f"{request.user.get_username()} (session)"
    return "family-admin token"


class FamilyView(APIView):
    """GET who is in, POST to add, DELETE to remove.

    GET also lists accounts that exist but are *not* in the family, because
    the question after "add Yotam" is almost always "what did he sign up as",
    and guessing at a username over a chat is how the wrong person gets let in.
    """

    permission_classes = [HasFamilyAdminToken]

    def get(self, request):
        User = get_user_model()
        members = User.objects.filter(groups__name=FAMILY_GROUP).order_by("date_joined")
        others = User.objects.exclude(groups__name=FAMILY_GROUP).exclude(is_superuser=True).order_by("-date_joined")
        return Response({
            "family": UserSummarySerializer(members, many=True).data,
            "accounts_not_in_family": [
                {"id": u.id, "username": u.get_username(), "email": u.email} for u in others[:50]
            ],
        })

    def post(self, request):
        user = _find_user(request.data.get("user"))
        if user is None:
            # Deliberately not "create them": see the module docstring.
            return Response(
                {"error": "no such account",
                 "detail": "They need to sign up at /ustrip/ first — this never creates accounts."},
                status=404,
            )
        group, _ = Group.objects.get_or_create(name=FAMILY_GROUP)
        already = user.groups.filter(name=FAMILY_GROUP).exists()
        if not already:
            user.groups.add(group)
            log.info("ustrip: %s added %s to the family", _actor(request), user.get_username())
        return Response(
            {"user": UserSummarySerializer(user).data, "in_family": True, "changed": not already},
            status=200 if already else 201,
        )

    def delete(self, request):
        user = _find_user(request.data.get("user") or request.query_params.get("user"))
        if user is None:
            return Response({"error": "no such account"}, status=404)
        was = user.groups.filter(name=FAMILY_GROUP).exists()
        if was:
            user.groups.remove(Group.objects.get(name=FAMILY_GROUP))
            log.info("ustrip: %s removed %s from the family", _actor(request), user.get_username())
        # The account itself is untouched — this only takes away ustrip.
        return Response({"user": UserSummarySerializer(user).data, "in_family": False, "changed": was})
