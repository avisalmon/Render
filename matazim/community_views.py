"""קהילת מט״צים: the feed inside the walls, and the page outside them.

REQ-M.26, REQ-M.131, REQ-M.132, REQ-M.133. Spec §4.12.

Three screens. A member reads the stream their institution writes and adds to
it; a program manager can take any row down and say why; and a stranger gets a
page that describes the community and shows no rows at all.

The last one is the rule most likely to be softened later, so it is stated here
as well as in the spec: an internal feed and a consented public gallery are
different products (REQ-M.30a). Building the first must not quietly open the
second.
"""

import logging

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .access import institution_of, is_program_manager, readable_posts, visible_posts
from .models import Post, Submission
from .views import shell

logger = logging.getLogger(__name__)

LOGIN_URL = "/matazim/login/"

# A post nobody typed anything into is not a post.
MIN_BODY = 2


def moderate(text, user):
    """(ok, why) — babook's engine, מט״צים's decision about what to do with it.

    §2.1: shared engine, our own views. `text_relevance_ok` fails open on any
    error, which is right, and means this is a filter rather than a guarantee.
    The guard that actually holds is the take-down below.
    """
    try:
        from app.safety import text_relevance_ok

        ok, _ = text_relevance_ok(text, context_label="matazim-community", user=user)
    except Exception:
        # Fail open, and the whole call is inside the try rather than just the
        # import. `text_relevance_ok` fails open on its own account, but "it
        # handles its own errors" is a property of somebody else's file, and
        # the cost of being wrong about it is a member losing what they wrote
        # to an outage. Same rule every AI call in this product follows.
        logger.exception("matazim community moderation failed open")
        return True, ""

    if ok:
        return True, ""
    return False, (
        "הטקסט הזה לא מתאים לקהילה. אם נראה לכם שזו טעות, "
        "אפשר לנסח מחדש או לפנות למנהלת התוכנית."
    )


def _shareable(user):
    """Work this person may put in the feed: their own, approved, not already in.

    REQ-M.132. Approved only, because the feed is not a place to be seen
    failing, and one's own only, because §4.10 says whose decision that is.
    """
    return (
        Submission.objects.filter(
            student__user=user, status=Submission.APPROVED, shared_as__isnull=True
        )
        .select_related("student")
        .order_by("-created_at")
    )


def community(request):
    """One door, and whoever opens it gets their own page.

    A visitor and a candidate get the page about what the community is
    (REQ-M.133); everybody who belongs to an institution gets the feed
    (REQ-M.26). One URL because the menu has one entry and a member should not
    have to learn a second address, and two screens because REQ-M.102 says a
    page shows the reader their own thing and nothing built for somebody else.

    This is not REQ-M.100's mistake in disguise. That was one screen carrying
    four roles' panels at once. This is two screens behind one door.
    """
    if institution_of(request.user) is None:
        return render(
            request, "matazim/community_about.html", shell(request, "community")
        )
    return feed(request)


@login_required(login_url=LOGIN_URL)
def feed(request):
    """REQ-M.26 — the stream itself."""
    institution = institution_of(request.user)
    error = ""

    if request.method == "POST":
        body = (request.POST.get("body") or "").strip()
        share_id = (request.POST.get("submission") or "").strip()

        if institution is None:
            # A candidate, or a member with no leader yet. Not an error in them:
            # they belong to no institution, so there is no room to write into.
            error = "עוד אין לכם קבוצה בתוכנית, אז אין לאן לכתוב. ברגע שתצטרפו למוביל/ה זה ייפתח."
        elif len(body) < MIN_BODY:
            error = "כדאי לכתוב משהו לפני ששולחים."
        else:
            ok, why = moderate(body, request.user)
            if not ok:
                error = why
            else:
                submission = None
                if share_id:
                    submission = _shareable(request.user).filter(pk=share_id).first()
                    if submission is None:
                        error = "התוצר הזה לא זמין לשיתוף."

                if not error:
                    Post.objects.create(
                        author=request.user,
                        institution=institution,
                        kind=(
                            Post.ANNOUNCEMENT
                            if is_program_manager(request.user)
                            else (Post.WORK if submission else Post.POST)
                        ),
                        body=body,
                        submission=submission,
                    )
                    return redirect("matazim:community")

    rows = readable_posts(request.user).select_related(
        "author", "author__profile", "submission"
    )[:60]

    return render(
        request,
        "matazim/community.html",
        shell(
            request,
            "community",
            posts=list(rows),
            error=error,
            posted=request.POST.get("body", "") if request.method == "POST" else "",
            shareable=list(_shareable(request.user)) if institution else [],
            has_room=institution is not None,
            can_moderate=is_program_manager(request.user),
        ),
    )


@require_POST
@login_required(login_url=LOGIN_URL)
def hide_post(request, post_id):
    """REQ-M.131 — taken down by a person, with a reason, never deleted.

    The reason is required for the same argument `submission_views` makes about
    returning work without words: an action that only says "no" tells the person
    it happened to that they failed, and not what to do about it.
    """
    if not is_program_manager(request.user):
        raise PermissionDenied

    post = get_object_or_404(visible_posts(request.user), pk=post_id)
    reason = (request.POST.get("reason") or "").strip()

    if not post.is_hidden and reason:
        post.hidden_at = timezone.now()
        post.hidden_by = request.user
        post.hidden_reason = reason
        post.save(update_fields=["hidden_at", "hidden_by", "hidden_reason"])

    return redirect("matazim:community")


@require_POST
@login_required(login_url=LOGIN_URL)
def show_post(request, post_id):
    """REQ-M.131 — a take-down is a person's judgement, so it can be a person's
    mistake.

    `docs/building_an_app.md`: the question to ask before calling a feature done
    is whether somebody can fix a mistake in it without going to `/admin/`. Hide
    without show fails that, and it fails it on the one action in this product
    that is aimed at a fourteen-year-old's words.
    """
    if not is_program_manager(request.user):
        raise PermissionDenied

    post = get_object_or_404(visible_posts(request.user), pk=post_id)
    if post.is_hidden:
        post.hidden_at = None
        post.hidden_by = None
        post.hidden_reason = ""
        post.save(update_fields=["hidden_at", "hidden_by", "hidden_reason"])

    return redirect("matazim:community")


@require_POST
@login_required(login_url=LOGIN_URL)
def unshare_post(request, post_id):
    """REQ-M.132 — the maker can take their work back out.

    Deleted rather than hidden, and that is the one deliberate exception to
    REQ-M.131: hiding exists so a moderated writer can see what happened to
    them, and there is nobody to explain anything to when the writer is the one
    withdrawing. Leaving the row would also mean a member who changed their mind
    still has a row in the institution's table saying they shared it.
    """
    post = get_object_or_404(visible_posts(request.user), pk=post_id, author=request.user)
    post.delete()
    return redirect("matazim:community")


