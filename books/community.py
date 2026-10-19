"""Community (spec BK7): threads, blog pieces and book reports, comments,
short reviews, the reading log, public profiles, and moderation. Every
change is one function here; pages and the API call these.

Decisions (2026-10-19, for Avi's ack): a thread is open to all of Books or a
circle's own; a circle's moderators moderate its threads and staff moderate
everything; hidden is reversible and deleting is the author's choice; no
contact details in a post (a phone number or an email is refused, the
request page is where people share those); a review is one per person per
book, 1 to 5, with a spoiler flag; the reading log is private unless the
person opens that part of their profile; no email digests (notifications
stay in the app, Avi's BK5 rule).
"""

import re

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from .circles import membership
from .hub import blocked_ids, notify
from .models import (
    CircleMember,
    Copy,
    Deal,
    Notification,
    Offer,
    Post,
    Profile,
    ReadingLog,
    Review,
    Thread,
)

PHONE_RE = re.compile(r"(?<!\d)(?:\+?972|0)[\s\-]?\d{1,2}[\s\-]?\d{3}[\s\-]?\d{4}(?!\d)")
EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
MAX_RATING = 5


class CommunityError(Exception):
    """A refused action; the message is a catalogue key (club.err.*)."""


def clean_body(body, limit=20000):
    body = (body or "").strip()[:limit]
    if not body:
        raise CommunityError("club.err.empty")
    if PHONE_RE.search(body) or EMAIL_RE.search(body):
        raise CommunityError("club.err.contact")
    return body


# ---- who may do what ---------------------------------------------------------------------

def can_read(profile, thread):
    if thread.circle_id is None:
        return True
    return membership(profile, thread.circle) is not None


def is_moderator(profile, thread):
    """Staff everywhere; a circle's moderators in its threads."""
    if profile.user.is_staff:
        return True
    if thread.circle_id is None:
        return False
    m = membership(profile, thread.circle)
    return bool(m and m.can_moderate)


def visible_threads(profile, kind=None, circle=None, entry=None, q=None):
    """Open threads plus the ones in my circles, hiding blocked people's."""
    mine = CircleMember.objects.filter(profile=profile).values("circle_id")
    qs = (Thread.objects.filter(Q(circle__isnull=True) | Q(circle_id__in=mine))
          .exclude(author_id__in=blocked_ids(profile))
          .select_related("author", "circle", "entry"))
    if kind:
        qs = qs.filter(kind=kind)
    if circle is not None:
        qs = qs.filter(circle=circle)
    if entry is not None:
        qs = qs.filter(entry=entry)
    if q:
        qs = qs.filter(title__icontains=q.strip()[:80])
    return qs


# ---- threads and posts ----------------------------------------------------------------------

@transaction.atomic
def start_thread(author, kind, title, body, circle=None, entry=None):
    if kind not in dict(Thread.KINDS):
        kind = Thread.DISCUSSION
    title = (title or "").strip()[:160]
    if not title:
        raise CommunityError("club.err.title")
    if circle is not None and membership(author, circle) is None:
        raise CommunityError("club.err.not_member")
    body = clean_body(body)
    thread = Thread.objects.create(kind=kind, circle=circle, author=author, title=title, entry=entry)
    Post.objects.create(thread=thread, author=author, body=body)
    return thread


def reply(author, thread, body):
    if not can_read(author, thread):
        raise CommunityError("club.err.not_member")
    if thread.is_locked and not is_moderator(author, thread):
        raise CommunityError("club.err.locked")
    if thread.author_id in blocked_ids(author):
        raise CommunityError("club.err.blocked")
    body = clean_body(body)
    post = Post.objects.create(thread=thread, author=author, body=body)
    Thread.objects.filter(pk=thread.pk).update(last_post_at=timezone.now())
    # One unread "new comment" per thread for its author is enough.
    if thread.author_id != author.pk and not Notification.objects.filter(
            profile=thread.author, thread=thread, kind="thread.reply", read_at__isnull=True).exists():
        notify(thread.author, "thread.reply", thread=thread)
    return post


def edit_post(actor, post, body):
    if post.author_id != actor.pk:
        raise CommunityError("club.err.not_yours")
    if post.status == Post.HIDDEN:
        raise CommunityError("club.err.hidden")
    post.body = clean_body(body)
    post.edited_at = timezone.now()
    post.save(update_fields=["body", "edited_at"])
    return post


@transaction.atomic
def delete_post(actor, post):
    """The author's own choice, final. Deleting a thread's first post
    deletes the thread with everything in it."""
    if post.author_id != actor.pk:
        raise CommunityError("club.err.not_yours")
    thread = post.thread
    first = thread.posts.order_by("created_at").first()
    if first and first.pk == post.pk:
        thread.delete()
        return None
    post.delete()
    return thread


def hide_post(actor, post, hidden=True):
    if not is_moderator(actor, post.thread):
        raise CommunityError("club.err.not_allowed")
    post.status = Post.HIDDEN if hidden else Post.VISIBLE
    post.hidden_by = actor if hidden else None
    post.save(update_fields=["status", "hidden_by"])
    return post


def lock_thread(actor, thread, locked=True):
    if not is_moderator(actor, thread):
        raise CommunityError("club.err.not_allowed")
    thread.is_locked = locked
    thread.save(update_fields=["is_locked"])
    return thread


def pin_thread(actor, thread, pinned=True):
    if not is_moderator(actor, thread):
        raise CommunityError("club.err.not_allowed")
    thread.is_pinned = pinned
    thread.save(update_fields=["is_pinned"])
    return thread


def posts_for(thread, viewer):
    """Visible posts, plus hidden ones for their author and for moderators
    (so a hidden post is seen as hidden, not gone)."""
    qs = thread.posts.select_related("author")
    if is_moderator(viewer, thread):
        return qs
    return qs.filter(Q(status=Post.VISIBLE) | Q(author=viewer))


# ---- reviews -------------------------------------------------------------------------------------

def set_review(profile, entry, rating, body="", has_spoilers=False):
    try:
        rating = int(rating)
    except (TypeError, ValueError):
        rating = 0
    if not 1 <= rating <= MAX_RATING:
        raise CommunityError("club.err.rating")
    body = (body or "").strip()[:4000]
    if body and (PHONE_RE.search(body) or EMAIL_RE.search(body)):
        raise CommunityError("club.err.contact")
    review, _ = Review.objects.update_or_create(
        profile=profile, entry=entry,
        defaults={"rating": rating, "body": body, "has_spoilers": bool(has_spoilers), "status": Review.VISIBLE})
    return review


def delete_review(profile, entry):
    Review.objects.filter(profile=profile, entry=entry).delete()


def hide_review(actor, review, hidden=True):
    if not actor.user.is_staff:
        raise CommunityError("club.err.not_allowed")
    review.status = Review.HIDDEN if hidden else Review.VISIBLE
    review.save(update_fields=["status"])
    return review


def reviews_for(entry, viewer):
    return (Review.objects.filter(entry=entry, status=Review.VISIBLE)
            .exclude(profile_id__in=blocked_ids(viewer)).select_related("profile"))


def rating_summary(entry):
    rows = Review.objects.filter(entry=entry, status=Review.VISIBLE).values_list("rating", flat=True)
    rows = list(rows)
    return {"count": len(rows), "average": round(sum(rows) / len(rows), 1) if rows else None}


# ---- the reading log --------------------------------------------------------------------------------

def log_reading(profile, entry, status, note="", started_on=None, finished_on=None):
    if status not in dict(ReadingLog.STATUSES):
        raise CommunityError("club.err.status")
    today = timezone.now().date()
    defaults = {"status": status, "note": (note or "").strip()[:500]}
    if status == ReadingLog.READING:
        defaults["started_on"] = started_on or today
    if status in (ReadingLog.READ, ReadingLog.DNF):
        defaults["finished_on"] = finished_on or today
    row, created = ReadingLog.objects.update_or_create(profile=profile, entry=entry, defaults=defaults)
    if not created and status == ReadingLog.READING and not row.started_on:
        row.started_on = today
        row.save(update_fields=["started_on"])
    return row


def unlog_reading(profile, entry):
    ReadingLog.objects.filter(profile=profile, entry=entry).delete()


# ---- public profiles ------------------------------------------------------------------------------

def public_view(person, viewer):
    """What `viewer` may see of `person`: nothing unless the profile is
    public and they are not blocked; then only the parts opted in."""
    if person.pk != viewer.pk and (not person.profile_public or person.pk in blocked_ids(viewer)):
        return None
    from .hub import reputation

    me = person.pk == viewer.pk
    view = {"person": person, "me": me, "rep": reputation(person), "library": [], "reading": [], "reviews": [],
            "threads": []}
    if me or person.public_library:
        view["library"] = list(Copy.objects.filter(owner=person, visibility=Copy.PUBLIC, status__in=Copy.HELD)
                               .select_related("entry").prefetch_related("offers").order_by("position")[:300])
    if me or person.public_reading:
        view["reading"] = list(ReadingLog.objects.filter(profile=person).select_related("entry")[:300])
    if me or person.public_reviews:
        view["reviews"] = list(Review.objects.filter(profile=person, status=Review.VISIBLE).select_related("entry")[:100])
    view["threads"] = list(Thread.objects.filter(author=person, circle__isnull=True).select_related("entry")[:50])
    view["offered"] = Offer.objects.filter(copy__owner=person, is_active=True, copy__visibility=Copy.PUBLIC,
                                           copy__status=Copy.WITH_OWNER).values("copy_id").distinct().count()
    view["completed"] = Deal.objects.filter(Q(owner=person) | Q(requester=person),
                                            status__in=[Deal.RETURNED, Deal.COMPLETED]).count()
    return view


def people_with_public_profiles(viewer, q=None):
    qs = Profile.objects.filter(profile_public=True).exclude(pk__in=blocked_ids(viewer)).exclude(pk=viewer.pk)
    if q:
        qs = qs.filter(display_name__icontains=q.strip()[:60])
    return qs.order_by("display_name")[:200]
