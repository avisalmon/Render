"""The improvement loop, over the wire (§4.11, REQ-M.105 to REQ-M.111).

Why this exists: נעמי writes requests on the site, Avi approves them, and the
sprint happens because Avi says so in conversation. That conversation happens in
a chat, often while he is away from a desk, and until now the third side of the
loop stopped dead at "somebody with database access reads the queue". The
requests themselves are reachable at `/matazim/api/requests/`, but that endpoint
takes a session cookie, which an agent in a chat does not have and must never be
given.

**What this deliberately cannot do.** A leaked token here must not be a way into
a site that holds other people's accounts, and must not be a way into the
programme's data about named minors. The blast radius is fenced by code:

  - It touches `Request` and `RequestMessage` and nothing else. No student, no
    leader, no submission, no certificate, no user record.
  - The three verbs are the three the loop has: read what is waiting, decide
    it, and record what was built. There is no create: a request is somebody's
    own words about their own experience, and a key that could write one could
    manufacture a mandate for work nobody asked for.
  - It never edits `body`. REQ-M.112 says the text is hers and is never
    rewritten, and that is enforced here rather than trusted.
  - It never touches a user: no password, no email, no `is_staff`, no
    `is_superuser`, no group.

So the worst a stolen token can do is read staff feedback about a website and
mark it decided. That is a real annoyance and not a breach of anything about a
teenager.

Auth is the convention `ustrip/family_api.py` and the backup trigger already
use: a shared secret from an environment variable, compared in constant time,
never in the repo. A logged-in superuser is allowed too, so the same endpoint
works from a browser without a token existing at all.

Every decision made through this is logged with who and how, because "who
approved this" deserves an answer that does not depend on memory.
"""

import logging

from django.conf import settings
from django.utils import timezone
from django.utils.crypto import constant_time_compare
from rest_framework import status
from rest_framework.permissions import BasePermission
from rest_framework.response import Response
from rest_framework.views import APIView

log = logging.getLogger(__name__)


class HasRequestAdminToken(BasePermission):
    """The token, or a superuser session. Nothing else, and closed by default."""

    def has_permission(self, request, view):
        user = getattr(request, "user", None)
        if user is not None and user.is_authenticated and user.is_superuser:
            return True

        expected = getattr(settings, "MATAZIM_ADMIN_TOKEN", "") or ""
        if not expected:
            # Fail shut. An unset secret means closed, never open: a deploy
            # that forgets the variable must lock the door rather than remove
            # it, which is the classic version of this mistake.
            return False

        header = request.headers.get("Authorization", "")
        presented = (
            header[7:] if header.startswith("Bearer ") else request.headers.get("X-Matazim-Token", "")
        )
        return bool(presented) and constant_time_compare(presented, expected)


def _who(request):
    user = getattr(request, "user", None)
    if user is not None and user.is_authenticated:
        return f"session:{user.username}"
    return "token"


def _row(row):
    """One request, as the person deciding it needs to read it.

    `body` is included in full and never truncated: the exact words are the
    evidence (REQ-M.112), and a queue that shows the first line teaches people
    to decide on first lines.
    """
    author = row.author
    return {
        "id": row.pk,
        "status": row.status,
        "kind": row.kind,
        "author": (getattr(getattr(author, "profile", None), "display_name", "") or author.get_username()),
        "author_role": row.author_role,
        "from_screen": row.from_screen,
        "body": row.body,
        "assessment": row.assessment,
        "sprint": row.sprint,
        "outcome": row.outcome,
        "created_at": row.created_at.isoformat(),
        "decided_at": row.decided_at.isoformat() if row.decided_at else None,
        "done_at": row.done_at.isoformat() if row.done_at else None,
        "summary_sent_at": row.summary_sent_at.isoformat() if row.summary_sent_at else None,
    }


class RequestQueueView(APIView):
    """Read the queue, decide a request, or record what was built for one."""

    permission_classes = [HasRequestAdminToken]

    def get(self, request):
        """`?status=approved` is the one a sprint starts from."""
        from .models import Request

        rows = Request.objects.select_related("author", "author__profile").order_by("-created_at")

        wanted = (request.query_params.get("status") or "").strip()
        if wanted:
            valid = {choice for choice, _ in Request.STATUS_CHOICES}
            if wanted not in valid:
                return Response(
                    {"detail": f"status must be one of {sorted(valid)}"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            rows = rows.filter(status=wanted)

        # A draft is somebody mid-sentence (REQ-M.107). It is not waiting for a
        # decision and does not belong in a queue somebody is working through.
        rows = rows.exclude(status=Request.DRAFT)

        counts = {}
        for choice, _ in Request.STATUS_CHOICES:
            if choice != Request.DRAFT:
                counts[choice] = Request.objects.filter(status=choice).count()

        return Response({"counts": counts, "requests": [_row(row) for row in rows[:100]]})

    def post(self, request):
        """Decide one request, or record what was built for it.

        `{"id": 3, "action": "approve"}`  → approved
        `{"id": 3, "action": "decline"}`  → declined
        `{"id": 3, "action": "done", "sprint": "SPR-M.48",
          "outcome": "...", "demo": "...", "mail": true}`
        """
        from .models import Request

        body = request.data if isinstance(request.data, dict) else {}
        row_id = body.get("id")
        action = (body.get("action") or "").strip()

        if not row_id:
            return Response({"detail": "id is required"}, status=status.HTTP_400_BAD_REQUEST)

        row = Request.objects.filter(pk=row_id).first()
        if row is None:
            return Response({"detail": "no such request"}, status=status.HTTP_404_NOT_FOUND)

        if action in ("approve", "decline"):
            # REQ-M.110 — deciding starts nothing. It moves the row and writes
            # who moved it. No job is queued, nobody is notified, no sprint is
            # scheduled. The trigger for work is Avi in conversation, every time.
            # not-a-student-status: Request, a feedback row has no StatusLog;
            # its record is decided_by and decided_at (see history.py's rule).
            row.status = (  # not-a-student-status: Request
                Request.APPROVED if action == "approve" else Request.DECLINED
            )
            row.decided_at = timezone.now()
            if getattr(request, "user", None) is not None and request.user.is_authenticated:
                row.decided_by = request.user
            row.save(update_fields=["status", "decided_at", "decided_by"])
            log.info("matazim request %s %sd by %s", row.pk, action, _who(request))
            return Response(_row(row))

        if action == "done":
            outcome = (body.get("outcome") or "").strip()
            if not outcome:
                # The same rule the leader's feedback has (REQ-M.123): a status
                # without words is a status that tells the person nothing.
                return Response(
                    {"detail": "outcome is required: say what was actually built"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            row.status = Request.DONE  # not-a-student-status: Request
            row.sprint = (body.get("sprint") or "").strip()
            row.outcome = outcome
            row.done_at = timezone.now()
            row.save(update_fields=["status", "sprint", "outcome", "done_at"])
            log.info("matazim request %s closed by %s, sprint %r", row.pk, _who(request), row.sprint)

            sent = []
            if body.get("mail"):
                from .request_mail import send_request_summary

                sent = send_request_summary(row, demo=(body.get("demo") or "").strip())
            return Response({**_row(row), "mailed_to": sent})

        return Response(
            {"detail": "action must be approve, decline or done"},
            status=status.HTTP_400_BAD_REQUEST,
        )
