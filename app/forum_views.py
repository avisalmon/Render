"""
EPIC-6.2 views: forums & Q&A. Read-public, interact via login (REQ-6.1.11).
Markdown rendering reuses the lesson renderer; moderation + rate limits from
app/community.py apply to every write.
"""
import json
import re

from django.contrib import messages
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render

from .community import (
    award_badge,
    award_points,
    category_meta,
    forum_categories,
    guidelines_accepted,
    interact_required,
    moderation_ok,
    notify,
    rate_limit_ok,
)
from .models import (
    Course,
    ForumPost,
    ForumThread,
    PostVote,
    ThreadSubscription,
    Video,
)


def _render_markdown(text):
    import markdown
    try:
        return markdown.markdown(text or "", extensions=["fenced_code", "tables", "nl2br"])
    except Exception:
        return "<p>" + (text or "").replace("\n", "<br>") + "</p>"


def _check_write(request, text):
    """Shared write gate: guidelines accepted, rate limit, moderation.
    Returns an error message or None. An inline accept-checkbox on the form
    (accept_guidelines) satisfies the gate without losing the typed post."""
    if not guidelines_accepted(request.user):
        if request.POST.get("accept_guidelines"):
            from .community import accept_guidelines
            accept_guidelines(request.user)
        else:
            return "כדי לפרסם, סמנו שקראתם את כללי הקהילה (פעם אחת בלבד)."
    if not rate_limit_ok(request.user):
        return "הגעת למגבלת הפרסומים לשעה. נסו שוב מאוחר יותר."
    if not moderation_ok(text, user=request.user):
        return "התוכן סומן על ידי מסנן התוכן שלנו. נסחו מחדש בבקשה."
    return None


# ---------------------------------------------------------------------------
# Browse (read-public)
# ---------------------------------------------------------------------------

def forum_home(request):
    """Categories + latest threads (REQ-6.2.1) + filters/search (REQ-6.2.4)."""
    qs = ForumThread.objects.filter(is_hidden=False).select_related(
        "author__profile", "course"
    ).annotate(num_posts=Count("posts"))

    category = request.GET.get("cat", "")
    if category:
        qs = qs.filter(category=category)
    tag = request.GET.get("tag", "")
    if tag:
        # JSONField __contains is unsupported on SQLite; icontains casts to text
        qs = qs.filter(tags__icontains=tag)
    query = request.GET.get("q", "").strip()
    if query:
        qs = qs.filter(Q(title__icontains=query) | Q(body__icontains=query))
        qs = qs.order_by("-is_canonical", "-is_pinned", "-updated_at")  # REQ-6.2.6
    flt = request.GET.get("filter", "")
    if flt == "unanswered":
        qs = qs.filter(kind="question").exclude(posts__is_accepted=True)
    elif flt == "mine" and request.user.is_authenticated:
        qs = qs.filter(author=request.user)
    elif flt == "following" and request.user.is_authenticated:
        sub_ids = ThreadSubscription.objects.filter(
            user=request.user, thread__isnull=False
        ).values_list("thread_id", flat=True)
        sub_cats = ThreadSubscription.objects.filter(
            user=request.user, thread__isnull=True
        ).exclude(category="").values_list("category", flat=True)
        qs = qs.filter(Q(id__in=list(sub_ids)) | Q(category__in=list(sub_cats)))

    cats = []
    counts = dict(
        ForumThread.objects.filter(is_hidden=False)
        .values_list("category").annotate(n=Count("id")).values_list("category", "n")
    )
    for slug, meta in forum_categories():
        cats.append({"slug": slug, "meta": meta, "count": counts.get(slug, 0)})

    return render(request, "app/community/forum_home.html", {
        "threads": qs[:30],
        "categories": cats,
        "active_category": category,
        "query": query,
        "active_filter": flt,
        "active_tag": tag,
    })


def thread_detail(request, thread_id):
    thread = get_object_or_404(
        ForumThread.objects.select_related("author__profile", "course", "video"),
        pk=thread_id, is_hidden=False,
    )
    posts = thread.posts.filter(is_hidden=False).select_related("author__profile")
    my_votes = set()
    is_subscribed = False
    if request.user.is_authenticated:
        my_votes = set(PostVote.objects.filter(
            user=request.user, post__thread=thread
        ).values_list("post_id", flat=True))
        is_subscribed = ThreadSubscription.objects.filter(
            user=request.user, thread=thread
        ).exists()
    answer_draft = ""
    if request.user.is_authenticated:
        answer_draft = request.session.pop("answer_draft", "")
    return render(request, "app/community/thread.html", {
        "thread": thread,
        "answer_draft": answer_draft,
        "thread_body_html": _render_markdown(thread.body),
        "posts": [
            {"obj": p, "html": _render_markdown(p.body), "voted": p.id in my_votes}
            for p in posts
        ],
        "is_subscribed": is_subscribed,
        "can_accept": request.user == thread.author or request.user.is_staff,
        "needs_guidelines": (
            request.user.is_authenticated and not guidelines_accepted(request.user)
        ),
    })


# ---------------------------------------------------------------------------
# Write (login + guidelines + moderation + rate limit)
# ---------------------------------------------------------------------------

@interact_required
def thread_new(request):
    """Create a question/discussion (REQ-6.2.3). Lesson deep-link pre-tags
    course/video (REQ-6.2.5)."""
    course = None
    video = None
    course_slug = request.GET.get("course") or request.POST.get("course") or ""
    if course_slug:
        course = Course.objects.filter(slug=course_slug).first()
    lesson_order = request.GET.get("lesson") or request.POST.get("lesson") or ""
    if course and lesson_order.isdigit():
        video = Video.objects.filter(course=course, lesson_order=int(lesson_order)).first()

    if request.method == "POST":
        title = request.POST.get("title", "").strip()[:200]
        body = request.POST.get("body", "").strip()[:20000]
        category = request.POST.get("category", "general")
        if category_meta(category) is None:
            category = "general"
        kind = request.POST.get("kind", "question")
        if not title or not body:
            messages.error(request, "כותרת ותוכן נדרשים")
        else:
            err = _check_write(request, f"{title}\n{body}")
            if err:
                messages.error(request, err)  # falls through; the form re-renders with the typed values
            else:
                tags = [t.strip() for t in request.POST.get("tags", "").split(",") if t.strip()][:6]
                if course and course.slug not in tags:
                    tags.append(course.slug)
                thread = ForumThread.objects.create(
                    category=category, kind=kind if kind in ("question", "discussion") else "question",
                    title=title, body=body, author=request.user,
                    tags=tags, course=course, video=video,
                )
                ThreadSubscription.objects.get_or_create(user=request.user, thread=thread)
                from .analytics import flash_event
                flash_event(request, "community_post")
                return redirect("forum_thread", thread_id=thread.pk)

    return render(request, "app/community/thread_new.html", {
        "categories": forum_categories(),
        "course": course,
        "video": video,
        "default_category": (course.domain if course else "general"),
        "needs_guidelines": not guidelines_accepted(request.user),
        "form_title": request.POST.get("title", ""),
        # carry text typed in the feed composer (REQ-6.12.1)
        "form_body": request.POST.get("body", "") or request.GET.get("draft", ""),
        "form_tags": request.POST.get("tags", ""),
    })


@interact_required
def post_answer(request, thread_id):
    thread = get_object_or_404(ForumThread, pk=thread_id, is_hidden=False)
    if request.method != "POST":
        return redirect("forum_thread", thread_id=thread_id)
    body = request.POST.get("body", "").strip()[:20000]
    if not body:
        messages.error(request, "תוכן נדרש")
        return redirect("forum_thread", thread_id=thread_id)
    err = _check_write(request, body)
    if err:
        messages.error(request, err)
        # Never lose the typed answer: stash it for the re-rendered composer
        request.session["answer_draft"] = body
        return redirect("forum_thread", thread_id=thread_id)
    post = ForumPost.objects.create(thread=thread, author=request.user, body=body)
    thread.save(update_fields=["updated_at"])
    if not ForumPost.objects.filter(author=request.user).exclude(pk=post.pk).exists():
        award_badge(request.user, "first_answer")
    # Notify the asker + subscribers (REQ-6.2.8)
    notify(thread.author, verb="answer", actor=request.user,
           text=f"תשובה חדשה על «{thread.title}»",
           url=f"/community/forum/thread/{thread.pk}/")
    for sub in ThreadSubscription.objects.filter(thread=thread).exclude(
        user__in=[request.user, thread.author]
    ).select_related("user"):
        notify(sub.user, verb="reply", actor=request.user,
               text=f"פעילות חדשה בשרשור «{thread.title}»",
               url=f"/community/forum/thread/{thread.pk}/")
    ThreadSubscription.objects.get_or_create(user=request.user, thread=thread)
    return redirect("forum_thread", thread_id=thread_id)


@interact_required
def vote_post(request, post_id):
    """Upvote-only toggle (DEC-38) + reputation (+2) (REQ-6.2.2)."""
    if request.method != "POST":
        return JsonResponse({"error": "method not allowed"}, status=405)
    post = get_object_or_404(ForumPost, pk=post_id, is_hidden=False)
    if post.author == request.user:
        return JsonResponse({"error": "self-vote"}, status=400)
    vote, created = PostVote.objects.get_or_create(post=post, user=request.user)
    if created:
        award_points(post.author, "upvote_received", ref=f"post:{post.pk}")
    else:
        vote.delete()
    return JsonResponse({"ok": True, "upvotes": post.votes.count(), "voted": created})


@interact_required
def accept_answer(request, post_id):
    """Asker (or staff) accepts an answer (REQ-6.2.2): +15, badges, notify."""
    if request.method != "POST":
        return redirect("forum_home")
    post = get_object_or_404(ForumPost.objects.select_related("thread"), pk=post_id)
    thread = post.thread
    if request.user != thread.author and not request.user.is_staff:
        return JsonResponse({"error": "forbidden"}, status=403)
    thread.posts.update(is_accepted=False)
    post.is_accepted = True
    post.save(update_fields=["is_accepted"])
    award_points(post.author, "accepted_answer", ref=f"post:{post.pk}")
    award_badge(post.author, "accepted_answer")
    from .analytics import flash_event
    flash_event(request, "answer_accepted")
    if post.author.forum_posts.filter(is_accepted=True).count() >= 10:
        award_badge(post.author, "mentor")
    notify(post.author, verb="accepted", actor=request.user,
           text=f"התשובה שלך על «{thread.title}» התקבלה! ‎+15 נקודות",
           url=f"/community/forum/thread/{thread.pk}/")
    return redirect("forum_thread", thread_id=thread.pk)


@interact_required
def subscribe_thread(request, thread_id):
    if request.method != "POST":
        return redirect("forum_thread", thread_id=thread_id)
    thread = get_object_or_404(ForumThread, pk=thread_id)
    sub = ThreadSubscription.objects.filter(user=request.user, thread=thread).first()
    if sub:
        sub.delete()
    else:
        ThreadSubscription.objects.get_or_create(user=request.user, thread=thread)
    return redirect("forum_thread", thread_id=thread_id)


# ---------------------------------------------------------------------------
# Staff curation (REQ-6.2.6)
# ---------------------------------------------------------------------------

@interact_required
def thread_curate(request, thread_id):
    if not request.user.is_staff or request.method != "POST":
        return JsonResponse({"error": "forbidden"}, status=403)
    thread = get_object_or_404(ForumThread, pk=thread_id)
    action = request.POST.get("action", "")
    if action == "pin":
        thread.is_pinned = not thread.is_pinned
    elif action == "canonical":
        thread.is_canonical = not thread.is_canonical
    elif action == "hide":
        thread.is_hidden = True
    thread.save()
    return redirect("forum_home") if action == "hide" else redirect(
        "forum_thread", thread_id=thread_id
    )


# ---------------------------------------------------------------------------
# AI assist (REQ-6.2.7) — fails open / falls back to keyword matching
# ---------------------------------------------------------------------------

_STOPWORDS = {"איך", "מה", "למה", "האם", "עם", "של", "את", "אני", "לא", "יש", "זה", "על"}


def _keyword_similar(title, limit=5):
    words = [w for w in re.findall(r"[\w'-]{3,}", title) if w not in _STOPWORDS][:8]
    if not words:
        return []
    q = Q()
    for w in words:
        q |= Q(title__icontains=w)
    return list(
        ForumThread.objects.filter(q, is_hidden=False)
        .order_by("-is_canonical", "-updated_at")[:limit]
    )


@interact_required
def forum_preview(request):
    """Markdown preview for composers (REQ-6.2.3: preview before post)."""
    if request.method != "POST":
        return JsonResponse({"error": "method not allowed"}, status=405)
    try:
        data = json.loads(request.body)
    except ValueError:
        return JsonResponse({"error": "bad json"}, status=400)
    return JsonResponse({"html": _render_markdown((data.get("text") or "")[:20000])})


@interact_required
def similar_threads(request):
    """REQ-6.2.7a: before posting, suggest existing threads + lessons."""
    if request.method != "POST":
        return JsonResponse({"error": "method not allowed"}, status=405)
    try:
        data = json.loads(request.body)
    except ValueError:
        return JsonResponse({"error": "bad json"}, status=400)
    title = (data.get("title") or "").strip()[:200]
    if len(title) < 8:
        return JsonResponse({"threads": [], "lessons": []})
    threads = _keyword_similar(title)
    words = [w for w in re.findall(r"[\w'-]{3,}", title) if w not in _STOPWORDS][:8]
    lessons = []
    if words:
        q = Q()
        for w in words:
            q |= Q(title__icontains=w)
        lessons = list(
            Video.objects.filter(q, course__is_published=True)
            .select_related("course")[:3]
        )
    return JsonResponse({
        "threads": [
            {"id": t.pk, "title": t.title, "url": f"/community/forum/thread/{t.pk}/",
             "canonical": t.is_canonical}
            for t in threads
        ],
        "lessons": [
            {"title": f"{v.course.title} - {v.title}",
             "url": f"/courses/{v.course.slug}/lesson/{v.lesson_order}/"}
            for v in lessons
        ],
    })


@interact_required
def summarize_thread(request, thread_id):
    """REQ-6.2.7b: AI summary for long threads; cached on the thread."""
    if request.method != "POST":
        return JsonResponse({"error": "method not allowed"}, status=405)
    thread = get_object_or_404(ForumThread, pk=thread_id, is_hidden=False)
    posts = list(thread.posts.filter(is_hidden=False))
    if len(posts) <= 10:
        return JsonResponse({"error": "thread too short"}, status=400)
    if thread.ai_summary:
        return JsonResponse({"summary": thread.ai_summary})
    from .ai_chat import _is_stub_mode, call_openai
    if _is_stub_mode():
        return JsonResponse({"error": "ai unavailable"}, status=503)
    convo = f"שאלה: {thread.title}\n{thread.body}\n\n" + "\n\n".join(
        f"תשובה ({p.author.profile.public_name}): {p.body[:800]}" for p in posts[:25]
    )
    result = call_openai(
        [{"role": "user", "content": convo[:12000]}],
        system_prompt="סכם את הדיון הבא בעברית ב-3-5 נקודות קצרות וענייניות. "
                      "אם יש תשובה מוסכמת - הדגש אותה.",
    )
    thread.ai_summary = result["content"][:3000]
    thread.save(update_fields=["ai_summary"])
    return JsonResponse({"summary": thread.ai_summary})


@interact_required
def draft_answer(request, thread_id):
    """REQ-6.2.7c: staff-only Avi Bot draft answer (returned, never auto-posted)."""
    if not request.user.is_staff:
        return JsonResponse({"error": "forbidden"}, status=403)
    if request.method != "POST":
        return JsonResponse({"error": "method not allowed"}, status=405)
    thread = get_object_or_404(ForumThread, pk=thread_id)
    from .ai_chat import _is_stub_mode, call_openai
    if _is_stub_mode():
        return JsonResponse({"error": "ai unavailable"}, status=503)
    context = ""
    if thread.video and thread.video.notes_markdown:
        context = f"\n\nחומר השיעור הרלוונטי:\n{thread.video.notes_markdown[:4000]}"
    result = call_openai(
        [{"role": "user", "content": f"{thread.title}\n\n{thread.body[:3000]}{context}"}],
        system_prompt="אתה Avi Bot של babook. נסח טיוטת תשובה קצרה, מעשית וחמה "
                      "בעברית לשאלה הבאה. אם חומר השיעור עונה - הפנה אליו.",
    )
    return JsonResponse({"draft": result["content"]})
