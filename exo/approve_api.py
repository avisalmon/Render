"""Approving someone from a chat, without handing over the house.

This is `building_an_app.md`'s BKM applied literally. The problem it solves:
every app ends up with one job that cannot be done from a conversation because
it is a write to production the UI deliberately does not expose. Here it is
"let this person into the builder" — and the tempting fix, a general admin API
key, is a skeleton key to every other app's accounts on a shared database, and
it *will* end up pasted into a transcript, because that is how it reaches the
agent that needs it.

So the scope is fenced by the code, and the worst case is bounded by what this
endpoint *can express* rather than by who holds the secret:

1. **One job.** It adds an existing account to `exo_members`. Nothing else.
2. **The privileged thing is named in code, never in the request.** There is no
   `group` parameter to abuse; a caller passing one gets `exo_members` anyway.
3. **It never creates the principal.** Unknown email → refused. Otherwise the
   key would be a way to manufacture users on a site that is not only Avi's.
4. **It never escalates.** No `is_staff`, no `is_superuser`, no password, no
   email change, no deletion.
5. **It fails shut.** An unset env var means closed — the classic bug is an
   empty expected value comparing equal to an empty header, so the emptiness
   is checked before the comparison.
6. **Constant-time compare**, because `==` on a secret leaks its length and
   prefix through timing.
7. **Every use is logged**, with who and how.
8. **A superuser session also works**, so it is usable from the browsable API
   and still works if the env var was never set.

Blast radius, stated plainly: somebody could approve a person into an ExO
idea builder. That sentence is only boring because of rules 1-4.
"""

import logging
import os

from django.contrib.auth import get_user_model
from django.utils.crypto import constant_time_compare
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .access import GROUP_NAME, approve, membership_for

log = logging.getLogger("exo.approve")
User = get_user_model()

TOKEN_ENV = "EXO_APPROVE_TOKEN"
HEADER = "HTTP_X_EXO_TOKEN"


def _token_ok(request):
    expected = (os.environ.get(TOKEN_ENV) or "").strip()
    if not expected:
        # Fail shut. Unset means closed, never "anything matches".
        return False
    presented = (request.META.get(HEADER) or "").strip()
    if not presented:
        return False
    return constant_time_compare(presented, expected)


class ApproveView(APIView):
    """POST {"email": "..."} → that existing account joins `exo_members`."""

    permission_classes = [AllowAny]  # the check below is the real gate

    def post(self, request):
        user = request.user
        by_session = bool(
            user and user.is_authenticated and user.is_superuser
        )
        by_token = _token_ok(request)
        if not (by_session or by_token):
            log.warning("exo approve refused: no valid token or superuser session")
            return Response(
                {"detail": "not authorised"}, status=status.HTTP_403_FORBIDDEN
            )

        email = (request.data.get("email") or "").strip()
        if not email:
            return Response(
                {"detail": "email is required"}, status=status.HTTP_400_BAD_REQUEST
            )

        target = User.objects.filter(email__iexact=email).first()
        if target is None:
            # Never create the principal (rule 3).
            log.warning("exo approve refused: no account for %s", email)
            return Response(
                {"detail": "no such account"}, status=status.HTTP_404_NOT_FOUND
            )

        membership = membership_for(target, create=True)
        approve(membership, by=user if by_session else None)
        log.info(
            "exo approve: %s added to %s via %s",
            email, GROUP_NAME, "session" if by_session else "token",
        )
        return Response({"email": email, "status": membership.status, "group": GROUP_NAME})
