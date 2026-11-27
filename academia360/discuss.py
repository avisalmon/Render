"""The committee's threads (spec 4.3 "Discuss", backlog E.2): a discussion
about a submission or about the program, its posts, mentions, and the
notifications they fire. Committee only, like the rest of the room; a post
is markdown, sanitized when shown (text.render_markdown), never trusted raw.

One function per act (open a thread, add a post, edit a post), each writing
its rows and logging through the API's own logger, so the page and the API
leave the same trail. Mentions are ticked from the list of members under the
post, not parsed out of the text: Hebrew names have spaces in them.
"""

from django.contrib import messages
from django.db.models import Count, F, Max, Q
from django.db.models.functions import Coalesce
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_http_methods

from . import access, mail, notify
from .access import committee_only
from .api import _snapshot as snapshot
from .api import log_change
from .models import Discussion, DiscussionPost, Program, Submission
from .text import render_markdown

MAX_TITLE = 200
MAX_BODY = 6000
LETTER_THREAD = "הערות על טיוטת המכתב"


def _program():
    return Program.objects.order_by("pk").first()


def clean(text, cap):
    return (text or "").replace("\r\n", "\n").strip()[:cap]


def members(exclude=None):
    """Who can be mentioned: the committee's members and the admins, by name,
    without the writer."""
    people = {u.pk: u for u in notify.committee_members() + notify.admins()}
    if exclude is not None:
        people.pop(exclude.pk, None)
    return sorted(people.values(), key=lambda u: (u.first_name or u.email or "").lower())


def mentions_from(data, me):
    """The members ticked under a post; junk ids and the writer are dropped."""
    wanted = {int(v) for v in data.getlist("mention") if str(v).isdigit()}
    return [u for u in members(exclude=me) if u.pk in wanted]


def threads(program, submission=None):
    """The round's threads, the last activity first."""
    qs = Discussion.objects.filter(Q(program=program) | Q(submission__participation__program=program))
    if submission is not None:
        qs = qs.filter(submission=submission)
    return list(qs.select_related("submission__participation__institution", "opened_by")
                .annotate(n_posts=Count("posts", distinct=True), last_at=Coalesce(Max("posts__created_at"), F("created_at")))
                .order_by("-last_at", "-pk"))


def participants(discussion):
    """Everyone in a thread so far: who opened it and who posted."""
    people = {}
    if discussion.opened_by_id and discussion.opened_by is not None:
        people[discussion.opened_by_id] = discussion.opened_by
    for p in discussion.posts.select_related("author"):
        if p.author_id:
            people[p.author_id] = p.author
    return list(people.values())


def open_thread(request, title, body="", submission=None, mentions=()):
    """A new thread, about a submission or (without one) about the program,
    with its first post when a body was written."""
    program = submission.participation.program if submission is not None else _program()
    row = Discussion.objects.create(submission=submission, program=None if submission is not None else program,
                                    title=title, opened_by=request.user)
    log_change(request, row)
    if body:
        add_post(request, row, body, mentions, first=True)
    elif mentions:
        notify.mentioned(mentions, _Opening(row), actor=request.user, base=mail.base_url(request))
    return row


class _Opening:
    """A thread opened without a first post still mentions people; the
    notification points at the thread itself."""

    def __init__(self, discussion):
        self.discussion = discussion
        self.pk = 0


def add_post(request, discussion, body, mentions=(), first=False):
    """One post; the mentioned are told by bell and mail, the thread's
    earlier people by bell (never the writer)."""
    post = DiscussionPost.objects.create(discussion=discussion, author=request.user, body=body)
    log_change(request, post)
    told = {u.pk for u in mentions}
    if mentions:
        notify.mentioned(mentions, post, actor=request.user, base=mail.base_url(request))
    if not first:
        others = [u for u in participants(discussion) if u.pk not in told]
        notify.new_post(others, post, actor=request.user)
    return post


def edit_post(request, post, body):
    before = snapshot(post)
    post.body = body
    post.edited_at = timezone.now()
    post.save(update_fields=["body", "edited_at", "updated_at"])
    log_change(request, post, before=before)
    return post


def may_edit(user, post):
    return access.is_admin(user) or post.author_id == user.pk


def letter_thread(submission):
    """The one thread that carries the comments on a letter's draft (E.4),
    made the first time anyone needs it."""
    row, created = Discussion.objects.get_or_create(submission=submission, title=LETTER_THREAD)
    return row


# -------------------------------------------------------------------- pages

def _submission_from(request):
    raw = request.POST.get("sub") or request.GET.get("sub") or ""
    if not str(raw).isdigit():
        return None
    return get_object_or_404(Submission.objects.select_related("participation__institution", "participation__program"), pk=int(raw))


@committee_only
@require_http_methods(["GET", "POST"])
def index(request):
    """The round's threads, and the form that opens one."""
    program = _program()
    if program is None:
        return render(request, "academia360/no_access.html", {"status": 404}, status=404)
    sub = _submission_from(request)
    if request.method == "POST":
        title = clean(request.POST.get("title"), MAX_TITLE)
        body = clean(request.POST.get("body"), MAX_BODY)
        if len(title) < 2:
            messages.error(request, "לדיון צריך כותרת.")
        else:
            row = open_thread(request, title, body, sub, mentions_from(request.POST, request.user))
            messages.success(request, "הדיון נפתח.")
            return redirect(reverse("academia360:committee_thread", args=[row.pk]))
    rows = threads(program, sub)
    return render(request, "academia360/committee/discuss.html", {
        "section": "committee", "rows": rows, "sub": sub, "inst": sub.participation.institution if sub else None,
        "members": members(exclude=request.user), "is_admin": access.is_admin(request.user),
    })


@committee_only
@require_http_methods(["GET", "POST"])
def thread(request, pk):
    """One thread: its posts, a reply, an edit of my own post."""
    row = get_object_or_404(Discussion.objects.select_related("submission__participation__institution", "opened_by"), pk=pk)
    if request.method == "POST":
        action = request.POST.get("action", "reply")
        body = clean(request.POST.get("body"), MAX_BODY)
        if action == "edit":
            post = get_object_or_404(DiscussionPost, pk=request.POST.get("post") or 0, discussion=row)
            if not may_edit(request.user, post):
                return access.no_access(request)
            if len(body) < 1:
                messages.error(request, "תגובה ריקה לא נשמרת; למחיקה יש הניהול.")
            else:
                edit_post(request, post, body)
                messages.success(request, "התגובה עודכנה.")
            return redirect(reverse("academia360:committee_thread", args=[row.pk]) + f"#post-{post.pk}")
        nxt = request.POST.get("next", "")
        back = nxt if (nxt.startswith("/academia360/") and  # the letter page posts from inline
                       url_has_allowed_host_and_scheme(nxt, allowed_hosts={request.get_host()})) else ""
        if len(body) < 1:
            messages.error(request, "התגובה ריקה.")
            return redirect(back or reverse("academia360:committee_thread", args=[row.pk]) + "#reply")
        post = add_post(request, row, body, mentions_from(request.POST, request.user))
        messages.success(request, "התגובה נוספה.")
        return redirect(back or reverse("academia360:committee_thread", args=[row.pk]) + f"#post-{post.pk}")
    posts = list(row.posts.select_related("author").order_by("created_at", "pk"))
    for p in posts:
        p.html = render_markdown(p.body)
        p.mine = may_edit(request.user, p)
    sub = row.submission
    return render(request, "academia360/committee/thread.html", {
        "section": "committee", "d": row, "posts": posts, "sub": sub,
        "inst": sub.participation.institution if sub else None,
        "members": members(exclude=request.user), "is_admin": access.is_admin(request.user),
    })
