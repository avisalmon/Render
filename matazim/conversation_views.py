"""Proposing a change, as a conversation (§4.11, REQ-M.115 to M.118).

Avi, 2026-09-13: "I want the experience of proposing an improvement to be like
a chat, so she will write what she wants, you will comment and suggest and
discuss, and there will be a button סיים שיחה ושלח בקשה when she just want to
submit."

Three views and one rule that outranks all of them.

**The conversation never stands between her and the button** (REQ-M.116).
`send` works on a draft with one message and no reply, on a draft mid-answer,
and on a draft where the model was unreachable for every turn. An assistant
that asks one more clarifying question before it will accept a complaint is a
suggestion box with extra steps.

**A draft is not a request** (REQ-M.117). It stays out of Avi's queue until she
sends it, and an abandoned one is not work anybody owes her an answer on.

**Post, redirect, get**, so a refresh after answering does not say the same
thing twice into a transcript somebody will read later.
"""

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .access import role_of
from .assess import discuss, proposed_wording, recommend, without_proposal
from .models import Request, RequestMessage
from .request_views import may_use_requests
from .views import shell

LOGIN_URL = "/matazim/login/"


def _my_draft(user, pk):
    """A draft of theirs, or nothing.

    Scoped by author rather than by role: a program manager has no business in
    another manager's unsent draft, and root has no reason to be in one either.
    An unsent draft is the most private thing in this product.
    """
    return get_object_or_404(Request, pk=pk, author=user, status=Request.DRAFT)


@login_required(login_url=LOGIN_URL)
def start(request):
    """REQ-M.115 — the first thing she types opens the conversation."""
    if not may_use_requests(request.user):
        raise PermissionDenied

    error = ""
    from_screen = (request.POST.get("from_screen") or request.GET.get("from") or "").strip()[:300]

    if request.method == "POST":
        body = (request.POST.get("body") or "").strip()
        kind = request.POST.get("kind") or Request.IDEA
        if len(body) < 5:
            error = "כתבו משפט או שניים על מה שצריך לשנות."
        else:
            draft = Request.objects.create(
                author=request.user,
                author_role=role_of(request.user),
                body=body,
                kind=kind if kind in dict(Request.KIND_CHOICES) else Request.IDEA,
                from_screen=from_screen,
                status=Request.DRAFT,
            )
            RequestMessage.objects.create(
                request=draft, who=RequestMessage.HER, body=body
            )
            reply = discuss(draft)
            if reply:
                RequestMessage.objects.create(
                    request=draft, who=RequestMessage.ASSISTANT, body=reply
                )
            return redirect("matazim:talk", request_id=draft.pk)

    return render(
        request,
        "matazim/request_new.html",
        shell(
            request,
            "requests",
            error=error,
            from_screen=from_screen,
            kinds=Request.KIND_CHOICES,
            posted=request.POST if request.method == "POST" else None,
        ),
    )


@login_required(login_url=LOGIN_URL)
def talk(request, request_id):
    """REQ-M.115, REQ-M.116 — one turn, and the send button on every screen."""
    if not may_use_requests(request.user):
        raise PermissionDenied

    draft = _my_draft(request.user, request_id)

    if request.method == "POST":
        said = (request.POST.get("body") or "").strip()
        if said:
            # REQ-M.112 — exactly as typed.
            RequestMessage.objects.create(
                request=draft, who=RequestMessage.HER, body=said
            )
            reply = discuss(draft)
            if reply:
                RequestMessage.objects.create(
                    request=draft, who=RequestMessage.ASSISTANT, body=reply
                )
        return redirect("matazim:talk", request_id=draft.pk)

    turns = list(draft.messages.all())
    last = turns[-1] if turns else None

    # The proposal is shown below as a control, so it is taken out of the
    # message body here or the same sentence appears twice. The stored text
    # keeps it: what the assistant actually said is the record.
    shown = [
        {
            "is_hers": turn.is_hers,
            "body": turn.body if turn.is_hers else without_proposal(turn.body),
        }
        for turn in turns
    ]
    return render(
        request,
        "matazim/request_talk.html",
        shell(
            request,
            "requests",
            draft=draft,
            messages=shown,
            # REQ-M.119 — an offer, not an edit. Only the newest one, because a
            # button attached to a suggestion three turns old would adopt
            # something the conversation has already moved past.
            proposal=(
                proposed_wording(last.body)
                if last and last.who == RequestMessage.ASSISTANT
                else ""
            ),
            # Said on the screen, because an empty reply otherwise reads as the
            # assistant ignoring her.
            model_quiet=not draft.messages.filter(who=RequestMessage.ASSISTANT).exists(),
        ),
    )


@require_POST
@login_required(login_url=LOGIN_URL)
def adopt(request, request_id):
    """REQ-M.119 — she takes the suggested wording as her own.

    Avi: "Her words stays. The chat can propose new wording." Those two live
    together only if adopting is her act rather than an edit applied to her. So
    the adopted text is stored as a turn of **hers**, because she chose it, and
    what she wrote first stays in the transcript where anybody can still read
    both and see which is which.
    """
    if not may_use_requests(request.user):
        raise PermissionDenied

    draft = _my_draft(request.user, request_id)
    last = draft.messages.last()
    wording = proposed_wording(last.body) if last and last.who == RequestMessage.ASSISTANT else ""

    if wording:
        RequestMessage.objects.create(request=draft, who=RequestMessage.HER, body=wording)
        # The request body follows what she has settled on. The original is not
        # lost: it is the first turn of the conversation, and always will be.
        draft.body = wording
        draft.save(update_fields=["body"])

    return redirect("matazim:talk", request_id=draft.pk)


@require_POST
@login_required(login_url=LOGIN_URL)
def send(request, request_id):
    """REQ-M.116, REQ-M.118 — she is done talking.

    Works whatever state the conversation is in, including one message and no
    reply. The recommendation is written here rather than during the chat,
    because it is for Avi and is built from the whole conversation.
    """
    if not may_use_requests(request.user):
        raise PermissionDenied

    draft = _my_draft(request.user, request_id)

    # REQ-M.108 — Avi's own arrive approved; asking him to approve his own
    # request is a ceremony with no reader.
    is_root = request.user.is_superuser
    # not-a-student-status: Request, no StatusLog
    draft.status = Request.APPROVED if is_root else Request.NEW
    draft.decided_by = request.user if is_root else None
    draft.decided_at = timezone.now() if is_root else None
    draft.save(update_fields=["status", "decided_by", "decided_at"])

    recommend(draft)
    return redirect("matazim:my_requests")


@require_POST
@login_required(login_url=LOGIN_URL)
def discard(request, request_id):
    """An abandoned conversation is not a backlog item (REQ-M.117)."""
    if not may_use_requests(request.user):
        raise PermissionDenied

    _my_draft(request.user, request_id).delete()
    return redirect("matazim:my_requests")
