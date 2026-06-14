"""Community activity feed (REQ-6.4.1).

A pure-Python aggregator that merges the community's activity sources into one
reverse-chronological stream. **No engagement-bait algorithm (DEC-40)** — items
are ordered strictly newest-first. Scope filters narrow *which* items show, never
*how* they rank.

Each feed item is a plain dict so templates stay simple and the merge is trivial
to test:
    {kind, timestamp, actor, actor_name, text, url, icon, domains}
"""

# how many recent rows to pull from each source before the merge
_PER_SOURCE = 50


def _profile_name(user):
    p = getattr(user, "profile", None)
    return p.public_name if p else (user.username if user else "")


def _tip_items():
    from .models import Tip
    out = []
    for t in Tip.objects.filter(is_hidden=False).select_related("author__profile")[:_PER_SOURCE]:
        out.append({
            "kind": "tip", "timestamp": t.created_at, "actor": t.author,
            "actor_name": _profile_name(t.author),
            "text": t.body[:140], "url": f"/community/tips/{t.pk}/",
            "icon": "bi-lightbulb-fill", "domains": list(t.tags or []),
        })
    return out


def _project_items():
    from .models import ShowcaseProject
    out = []
    qs = (ShowcaseProject.objects.filter(status="published", is_hidden=False)
          .select_related("author__profile")[:_PER_SOURCE])
    for p in qs:
        out.append({
            "kind": "project", "timestamp": p.published_at or p.created_at,
            "actor": p.author, "actor_name": _profile_name(p.author),
            "text": p.title, "url": f"/community/showcase/p/{p.pk}/",
            "icon": "bi-easel2-fill", "domains": list(p.tags or []),
        })
    return out


def _thread_items():
    from .models import ForumThread
    out = []
    for th in ForumThread.objects.filter(is_hidden=False).select_related("author__profile")[:_PER_SOURCE]:
        out.append({
            "kind": "thread", "timestamp": th.created_at, "actor": th.author,
            "actor_name": _profile_name(th.author),
            "text": th.title, "url": f"/community/forum/thread/{th.pk}/",
            "icon": "bi-question-circle-fill" if th.kind == "question" else "bi-chat-square-text-fill",
            "domains": [th.category] if th.category else [],
        })
    return out


def _answer_items():
    from .models import ForumPost
    out = []
    qs = (ForumPost.objects.filter(is_accepted=True, is_hidden=False)
          .select_related("author__profile", "thread")[:_PER_SOURCE])
    for post in qs:
        out.append({
            "kind": "answer", "timestamp": post.created_at, "actor": post.author,
            "actor_name": _profile_name(post.author),
            "text": post.thread.title, "url": f"/community/forum/thread/{post.thread_id}/",
            "icon": "bi-check-circle-fill",
            "domains": [post.thread.category] if post.thread.category else [],
        })
    return out


def _badge_items():
    from .community import BADGES
    from .models import BadgeAward
    out = []
    for b in BadgeAward.objects.select_related("user__profile")[:_PER_SOURCE]:
        meta = BADGES.get(b.slug, {"title": b.slug})
        out.append({
            "kind": "badge", "timestamp": b.awarded_at, "actor": b.user,
            "actor_name": _profile_name(b.user),
            "text": meta["title"], "url": f"/c/{b.user.username}/",
            "icon": "bi-award-fill", "domains": [],
        })
    return out


def _event_items():
    from django.utils import timezone

    from .models import CommunityEvent
    out = []
    qs = (CommunityEvent.objects.filter(end_at__gte=timezone.now())
          .select_related("host__profile")[:_PER_SOURCE])
    for e in qs:
        out.append({
            "kind": "event", "timestamp": e.created_at,
            "actor": e.host, "actor_name": _profile_name(e.host) if e.host else "babook",
            "text": f"{e.title} · {e.start_at:%d/%m %H:%M}", "url": f"/community/events/{e.slug}/",
            "icon": "bi-calendar-event-fill", "domains": [],
        })
    return out


def build_feed(user, scope="all", limit=40):
    """Return the merged, newest-first activity list for `scope`.

    scope: "all" (everyone), "following" (people you follow + yourself),
    "domain" (items tagged with one of your interests). The last two require an
    authenticated user; otherwise they fall back to "all".
    """
    authed = bool(user and getattr(user, "is_authenticated", False))
    if not authed:
        scope = "all"

    items = (_tip_items() + _project_items() + _thread_items()
             + _answer_items() + _badge_items() + _event_items())

    if scope == "following":
        from .models import Follow
        followed = set(
            Follow.objects.filter(follower=user).values_list("followed_id", flat=True)
        )
        followed.add(user.pk)
        items = [it for it in items if it["actor"] and it["actor"].pk in followed]
    elif scope == "domain":
        learner = getattr(user, "learner_profile", None)
        interests = set(learner.interests or []) if learner else set()
        items = [it for it in items if interests.intersection(it["domains"])]

    items.sort(key=lambda it: it["timestamp"], reverse=True)
    return items[:limit]
