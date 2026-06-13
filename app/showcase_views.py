"""
EPIC-6.3 views: the showcase — דוכן השוויץ. Wall + brag feed + project
pages + create/edit + reactions + comments. Read-public; every interaction
requires login (REQ-6.1.11). Markdown + moderation reused from the forum.
"""
import re

from django.contrib import messages
from django.db.models import Count
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .community import (
    award_badge,
    award_points,
    guidelines_accepted,
    interact_required,
    is_student,
    moderation_ok,
    notify,
    rate_limit_ok,
    showcase_stands,
    stand_meta,
)
from .forum_views import _render_markdown
from .models import (
    Course,
    ProjectComment,
    ProjectImage,
    ProjectReaction,
    ShowcaseProject,
)

REACTION_KINDS = {"star": "⭐", "fire": "🔥", "love": "❤️", "clap": "👏", "wow": "🤯"}
RISING_STAR_THRESHOLD = 25


def _embed_url(url):
    """YouTube/Bunny watch URL → embeddable iframe src."""
    if not url:
        return ""
    m = re.search(r"(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/embed/)([\w-]{11})", url)
    if m:
        return f"https://www.youtube.com/embed/{m.group(1)}"
    if "iframe.mediadelivery.net" in url or "/embed/" in url:
        return url
    return ""


def _published(qs=None):
    qs = qs if qs is not None else ShowcaseProject.objects.all()
    return qs.filter(status="published", is_hidden=False)


# ---------------------------------------------------------------------------
# One-time site screenshot → stored as the project cover (REQ-6.3.17).
# Free screenshot service (thum.io), NO token / OpenAI cost. Runs in the
# background so publishing stays instant; the card then loads the stored image.
# ---------------------------------------------------------------------------

def capture_site_cover(project_id):
    """Fetch a screenshot of the project's site once and save it as the cover.
    Best-effort: on any failure the card keeps its live-screenshot fallback."""
    import urllib.request

    from django.core.files.base import ContentFile
    from django.db import close_old_connections
    close_old_connections()
    try:
        p = ShowcaseProject.objects.filter(pk=project_id).first()
        if not p or p.cover or not p.site_url:
            return
        url = "https://image.thum.io/get/width/1000/crop/675/noanimate/" + p.site_url
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        data = urllib.request.urlopen(req, timeout=45).read()
        if data and len(data) > 3000:  # sanity: a real image, not an error page
            p.cover.save(f"site_{p.pk}.jpg", ContentFile(data), save=True)
    except Exception:
        pass
    finally:
        close_old_connections()


def maybe_capture_cover(project):
    """Kick off a background capture if the project has a live site but no cover."""
    if project.cover or not project.site_url:
        return
    import threading
    threading.Thread(target=capture_site_cover, args=(project.pk,), daemon=True).start()


# ---------------------------------------------------------------------------
# Wall + brag feed (read-public)
# ---------------------------------------------------------------------------

def showcase_wall(request, stand=None):
    """REQ-6.3.2 / 6.3.8: the curated wall, optionally scoped to a stand."""
    qs = _published().select_related("author__profile", "course")
    active_stand = stand
    if stand and stand_meta(stand):
        qs = qs.filter(stand=stand)
    course_slug = request.GET.get("course", "")
    if course_slug:
        qs = qs.filter(course__slug=course_slug)
    tag = request.GET.get("tag", "")
    if tag:
        # JSONField __contains is unsupported on SQLite; icontains casts to
        # text and substring-matches the tag list, which is what we want.
        qs = qs.filter(tags__icontains=tag)
    sort = request.GET.get("sort", "new")
    qs = qs.order_by("-star_count", "-published_at") if sort == "top" else qs.order_by("-published_at")

    featured = []
    if not stand and not course_slug and not tag:
        featured = list(_published().filter(is_featured=True)
                        .select_related("author__profile")[:3])

    stands = []
    counts = dict(
        _published().values_list("stand").annotate(n=Count("id")).values_list("stand", "n")
    )
    for slug, meta in showcase_stands():
        stands.append({"slug": slug, "meta": meta, "count": counts.get(slug, 0)})

    return render(request, "app/community/showcase_wall.html", {
        "projects": qs[:40],
        "featured": featured,
        "stands": stands,
        "active_stand": active_stand,
        "active_stand_meta": stand_meta(stand) if stand else None,
        "sort": sort,
        "active_tag": tag,
    })


def showcase_feed(request):
    """REQ-6.3.11: the flowing brag feed — newest projects with live reactions."""
    projects = (
        _published().select_related("author__profile", "course")
        .order_by("-published_at")[:30]
    )
    return render(request, "app/community/showcase_feed.html", {"projects": projects})


def project_detail(request, project_id):
    project = get_object_or_404(
        ShowcaseProject.objects.select_related("author__profile", "course"),
        pk=project_id,
    )
    if not project.is_live and request.user != project.author and not request.user.is_staff:
        from django.http import Http404
        raise Http404("not published")

    # Backfill: capture the cover once for existing live-site projects (REQ-6.3.17)
    maybe_capture_cover(project)

    my_reactions = set()
    if request.user.is_authenticated:
        my_reactions = set(ProjectReaction.objects.filter(
            project=project, user=request.user
        ).values_list("kind", flat=True))
    reaction_counts = {
        r["kind"]: r["n"] for r in
        project.reactions.values("kind").annotate(n=Count("id"))
    }
    comments = project.comments.filter(is_hidden=False).select_related("author__profile")
    more = (
        _published(ShowcaseProject.objects.filter(author=project.author))
        .exclude(pk=project.pk)[:3]
    )
    return render(request, "app/community/project_detail.html", {
        "project": project,
        "story_html": _render_markdown(project.story),
        "embed_url": _embed_url(project.video_url),
        "gallery": project.images.all(),
        "reaction_kinds": REACTION_KINDS,
        "reaction_counts": reaction_counts,
        "my_reactions": my_reactions,
        "comments": [
            {"obj": c, "html": _render_markdown(c.body)} for c in comments
        ],
        "more_projects": more,
        "can_message": (
            request.user.is_authenticated
            and request.user != project.author
            and not is_student(request.user)
            and not is_student(project.author)
        ),
    })


# ---------------------------------------------------------------------------
# Create / edit / publish (login)
# ---------------------------------------------------------------------------

@interact_required
def project_create(request):
    course = None
    course_slug = request.GET.get("course") or request.POST.get("course") or ""
    if course_slug:
        course = Course.objects.filter(slug=course_slug).first()

    if request.method == "POST":
        return _save_project(request, None, course)

    return render(request, "app/community/project_form.html", {
        "stands": showcase_stands(),
        "course": course,
        "project": None,
        "needs_guidelines": not guidelines_accepted(request.user),
    })


@interact_required
def project_edit(request, project_id):
    project = get_object_or_404(ShowcaseProject, pk=project_id)
    if project.author != request.user and not request.user.is_staff:
        from django.http import HttpResponseForbidden
        return HttpResponseForbidden()
    if request.method == "POST":
        return _save_project(request, project, project.course)
    return render(request, "app/community/project_form.html", {
        "stands": showcase_stands(),
        "course": project.course,
        "project": project,
        "needs_guidelines": not guidelines_accepted(request.user),
    })


def _save_project(request, project, course):
    title = request.POST.get("title", "").strip()[:200]
    story = request.POST.get("story", "").strip()[:20000]
    stand = request.POST.get("stand", "other")
    if stand_meta(stand) is None:
        stand = "other"
    if not title:
        messages.error(request, "צריך כותרת לפרויקט")
        return render(request, "app/community/project_form.html", {
            "stands": showcase_stands(), "course": course, "project": project,
            "needs_guidelines": not guidelines_accepted(request.user),
            "form_title": title, "form_story": story,
        })

    publish = request.POST.get("action") == "publish"
    if publish:
        if not guidelines_accepted(request.user) and not request.POST.get("accept_guidelines"):
            messages.error(request, "כדי לפרסם, סמנו שקראתם את כללי הקהילה")
            return render(request, "app/community/project_form.html", {
                "stands": showcase_stands(), "course": course, "project": project,
                "needs_guidelines": True, "form_title": title, "form_story": story,
            })
        if request.POST.get("accept_guidelines"):
            from .community import accept_guidelines
            accept_guidelines(request.user)
        if not moderation_ok(f"{title}\n{story}", user=request.user):
            messages.error(request, "התוכן סומן על ידי מסנן התוכן. נסחו מחדש בבקשה.")
            return render(request, "app/community/project_form.html", {
                "stands": showcase_stands(), "course": course, "project": project,
                "needs_guidelines": False, "form_title": title, "form_story": story,
            })

    is_new = project is None
    if is_new:
        project = ShowcaseProject(author=request.user)
    project.title = title
    project.tagline = request.POST.get("tagline", "").strip()[:200]
    project.story = story
    project.stand = stand
    project.video_url = request.POST.get("video_url", "").strip()[:500]
    project.repo_url = request.POST.get("repo_url", "").strip()[:500]
    project.live_url = request.POST.get("live_url", "").strip()[:500]
    project.course = course
    project.tags = [t.strip() for t in request.POST.get("tags", "").split(",") if t.strip()][:6]
    if request.FILES.get("cover"):
        project.cover = request.FILES["cover"]

    was_published = (not is_new) and project.status == "published"
    if publish:
        # Student work goes to a review queue first (REQ-6.3.7)
        if is_student(request.user) and not was_published:
            project.status = "pending"
            messages.info(request, "הפרויקט נשלח לבדיקה קצרה ויפורסם בקרוב 🙂")
        else:
            newly = project.status != "published"
            project.status = "published"
            if not project.published_at:
                project.published_at = timezone.now()
            if newly:
                _on_publish(request, project)
    elif is_new:
        project.status = "draft"
    project.save()

    for f in request.FILES.getlist("gallery")[:8]:
        ProjectImage.objects.create(project=project, image=f)

    # Snapshot the live site once → stored cover (REQ-6.3.17), no token cost
    maybe_capture_cover(project)

    return redirect("showcase_project", project_id=project.pk)


def _on_publish(request, project):
    """Gamification + notifications on a first publish (REQ-6.3.13/6.3.14)."""
    award_points(request.user, "showcase_published", ref=f"project:{project.pk}")
    first = award_badge(request.user, "builder")
    n = ShowcaseProject.objects.filter(author=request.user, status="published").count() + 1
    master = award_badge(request.user, "showcase_master") if n >= 5 else None
    # The bragging payoff, felt immediately (UX): a celebratory toast
    reward = "פורסם! 🎉 ‎+10 נקודות"
    if first:
        reward += " והתג «בונה» 🔨"
    elif master:
        reward += " והתג «אמן התצוגה» 🎨"
    messages.success(request, reward)
    # Notify followers (REQ-6.1.5 graph)
    from .models import Follow
    for f in Follow.objects.filter(followed=request.user).select_related("follower"):
        notify(f.follower, verb="project", actor=request.user,
               text=f"{request.user.profile.public_name} פרסמ/ה פרויקט: {project.title}",
               url=f"/community/showcase/p/{project.pk}/")


@interact_required
def project_delete(request, project_id):
    project = get_object_or_404(ShowcaseProject, pk=project_id)
    if project.author != request.user and not request.user.is_staff:
        from django.http import HttpResponseForbidden
        return HttpResponseForbidden()
    if request.method == "POST":
        project.delete()
        return redirect("showcase_wall")
    return redirect("showcase_project", project_id=project_id)


# ---------------------------------------------------------------------------
# Reactions + comments
# ---------------------------------------------------------------------------

@interact_required
def project_react(request, project_id):
    """REQ-6.3.3: toggle a star/emoji reaction; star drives ranking + points."""
    if request.method != "POST":
        return JsonResponse({"error": "method not allowed"}, status=405)
    project = get_object_or_404(ShowcaseProject, pk=project_id)
    kind = request.POST.get("kind", "star")
    if kind not in REACTION_KINDS:
        return JsonResponse({"error": "bad kind"}, status=400)
    if project.author == request.user:
        return JsonResponse({"error": "self"}, status=400)
    reaction, created = ProjectReaction.objects.get_or_create(
        project=project, user=request.user, kind=kind
    )
    if not created:
        reaction.delete()
    if kind == "star":
        project.star_count = project.reactions.filter(kind="star").count()
        project.save(update_fields=["star_count"])
        if created:
            award_points(project.author, "showcase_star", ref=f"project:{project.pk}")
            if project.star_count == RISING_STAR_THRESHOLD:
                award_badge(project.author, "rising_star")
            notify(project.author, verb="reaction", actor=request.user,
                   text=f"{request.user.profile.public_name} העניק/ה כוכב לפרויקט «{project.title}»",
                   url=f"/community/showcase/p/{project.pk}/")
    count = project.reactions.filter(kind=kind).count()
    return JsonResponse({"ok": True, "kind": kind, "count": count, "on": created})


@interact_required
def project_comment(request, project_id):
    """REQ-6.3.10: comment on a project (moderated)."""
    project = get_object_or_404(ShowcaseProject, pk=project_id)
    if request.method != "POST":
        return redirect("showcase_project", project_id=project_id)
    body = request.POST.get("body", "").strip()[:5000]
    if not body:
        return redirect("showcase_project", project_id=project_id)
    if not guidelines_accepted(request.user) and not request.POST.get("accept_guidelines"):
        messages.error(request, "כדי להגיב, סמנו שקראתם את כללי הקהילה")
        return redirect("showcase_project", project_id=project_id)
    if request.POST.get("accept_guidelines"):
        from .community import accept_guidelines
        accept_guidelines(request.user)
    if not rate_limit_ok(request.user):
        messages.error(request, "הגעת למגבלת הפרסומים לשעה. נסו שוב מאוחר יותר.")
        return redirect("showcase_project", project_id=project_id)
    if not moderation_ok(body, user=request.user):
        messages.error(request, "התגובה סומנה על ידי מסנן התוכן. נסחו מחדש.")
        return redirect("showcase_project", project_id=project_id)
    ProjectComment.objects.create(project=project, author=request.user, body=body)
    notify(project.author, verb="comment", actor=request.user,
           text=f"{request.user.profile.public_name} הגיב/ה על «{project.title}»",
           url=f"/community/showcase/p/{project.pk}/")
    return redirect("showcase_project", project_id=project_id)


@interact_required
def project_feature(request, project_id):
    """Staff: toggle נבחרת השבוע (REQ-6.3.13)."""
    if not request.user.is_staff or request.method != "POST":
        return JsonResponse({"error": "forbidden"}, status=403)
    project = get_object_or_404(ShowcaseProject, pk=project_id)
    project.is_featured = not project.is_featured
    project.save(update_fields=["is_featured"])
    if project.is_featured:
        award_points(project.author, "showcase_featured", ref=f"project:{project.pk}")
        award_badge(project.author, "featured")
        notify(project.author, verb="featured", actor=request.user,
               text=f"הפרויקט «{project.title}» נבחר לנבחרת השבוע! 🎉",
               url=f"/community/showcase/p/{project.pk}/")
    return redirect("showcase_project", project_id=project_id)
