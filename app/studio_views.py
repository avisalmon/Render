"""Course Authoring Studio views (EPIC-4)."""
import json

import markdown as md
from django.contrib import messages
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.text import slugify
from django.views.decorators.http import require_POST

from .authoring.access import author_required
from .models import AuthoringJob, Course, Video
from .taxonomy import TRAINING_TAXONOMY

MD_EXT = ["fenced_code", "tables", "nl2br"]


def _domains_for_form():
    """[(domain_key, domain_title, [(track_key, track_title), ...])] for dropdowns."""
    out = []
    for dkey, dmeta in sorted(TRAINING_TAXONOMY.items(), key=lambda kv: kv[1]["order"]):
        tracks = [(tk, tm["title"]) for tk, tm in
                  sorted(dmeta["tracks"].items(), key=lambda kv: kv[1]["order"])]
        out.append((dkey, dmeta["title"], tracks))
    return out


def _clean(s):
    return (s or "").replace("—", ",").replace("–", "-")


@author_required
def studio_home(request):
    courses = Course.objects.all().order_by("-created_at")
    jobs = AuthoringJob.objects.exclude(status="done").order_by("-created_at")[:10]
    return render(request, "app/studio/home.html", {"courses": courses, "jobs": jobs})


@author_required
def course_create(request):
    if request.method == "POST":
        title = _clean(request.POST.get("title", "").strip())
        if not title:
            messages.error(request, "צריך כותרת לקורס")
            return redirect("studio_course_create")
        slug = request.POST.get("slug", "").strip() or slugify(title)
        base, k = slug, 2
        while Course.objects.filter(slug=slug).exists():
            slug = f"{base}-{k}"
            k += 1
        course = Course.objects.create(
            title=title, slug=slug,
            description=_clean(request.POST.get("description", "")),
            domain=request.POST.get("domain", "matazim"),
            track=request.POST.get("track", ""),
            difficulty=request.POST.get("difficulty", "beginner"),
            thumbnail=request.POST.get("thumbnail", "").strip(),
            is_published=False,
        )
        messages.success(request, "הקורס נוצר. אפשר להוסיף שיעורים.")
        return redirect("studio_course_edit", slug=course.slug)
    return render(request, "app/studio/course_form.html",
                  {"course": None, "domains": _domains_for_form()})


@author_required
def course_edit(request, slug):
    course = get_object_or_404(Course, slug=slug)
    if request.method == "POST":
        course.title = _clean(request.POST.get("title", course.title).strip())
        course.description = _clean(request.POST.get("description", ""))
        course.domain = request.POST.get("domain", course.domain)
        course.track = request.POST.get("track", "")
        course.difficulty = request.POST.get("difficulty", course.difficulty)
        course.thumbnail = request.POST.get("thumbnail", "").strip()
        course.is_published = request.POST.get("is_published") == "on"
        course.save()
        messages.success(request, "הקורס נשמר.")
        return redirect("studio_course_edit", slug=course.slug)
    return render(request, "app/studio/course_edit.html", {
        "course": course,
        "lessons": course.videos.order_by("lesson_order"),
        "domains": _domains_for_form(),
    })


@author_required
@require_POST
def course_delete(request, slug):
    course = get_object_or_404(Course, slug=slug)
    course.delete()
    messages.success(request, "הקורס נמחק.")
    return redirect("studio_home")


@author_required
@require_POST
def course_publish(request, slug):
    course = get_object_or_404(Course, slug=slug)
    course.is_published = not course.is_published
    course.save(update_fields=["is_published"])
    return redirect("studio_course_edit", slug=course.slug)


@author_required
def lesson_edit(request, slug, order=None):
    course = get_object_or_404(Course, slug=slug)
    lesson = None
    if order is not None:
        lesson = get_object_or_404(Video, course=course, lesson_order=order)
    if request.method == "POST":
        title = _clean(request.POST.get("title", "").strip()) or "שיעור"
        notes = _clean(request.POST.get("notes_markdown", ""))
        bunny = request.POST.get("bunny_video_id", "").strip()
        reflect = _clean(request.POST.get("reflection_prompt", "").strip())
        free = request.POST.get("is_free_preview") == "on"
        dur = int(request.POST.get("duration_seconds") or 0)
        if lesson is None:
            nxt = (course.videos.order_by("-lesson_order").first())
            new_order = (nxt.lesson_order + 1) if nxt else 1
            lesson = Video(course=course, lesson_order=new_order)
        lesson.title = title
        lesson.notes_markdown = notes
        lesson.bunny_video_id = bunny
        lesson.reflection_prompt = reflect
        lesson.is_free_preview = free
        lesson.duration_seconds = dur
        lesson.save()
        _fix_final_flag(course)
        messages.success(request, "השיעור נשמר.")
        return redirect("studio_course_edit", slug=course.slug)
    return render(request, "app/studio/lesson_form.html", {"course": course, "lesson": lesson})


@author_required
@require_POST
def lesson_delete(request, slug, order):
    course = get_object_or_404(Course, slug=slug)
    get_object_or_404(Video, course=course, lesson_order=order).delete()
    _fix_final_flag(course)
    return redirect("studio_course_edit", slug=course.slug)


@author_required
@require_POST
def lesson_reorder(request, slug):
    course = get_object_or_404(Course, slug=slug)
    try:
        ids = json.loads(request.body).get("order", [])
    except ValueError:
        return JsonResponse({"error": "bad json"}, status=400)
    # Two-phase to avoid unique (course, lesson_order) clashes.
    vids = {v.id: v for v in course.videos.all()}
    for i, vid in enumerate(ids):
        v = vids.get(int(vid))
        if v:
            v.lesson_order = 1000 + i
            v.save(update_fields=["lesson_order"])
    for i, vid in enumerate(ids, 1):
        v = vids.get(int(vid))
        if v:
            v.lesson_order = i
            v.save(update_fields=["lesson_order"])
    _fix_final_flag(course)
    return JsonResponse({"ok": True})


def _fix_final_flag(course):
    vids = list(course.videos.order_by("lesson_order"))
    for i, v in enumerate(vids):
        final = (i == len(vids) - 1)
        if v.is_final_lesson != final:
            v.is_final_lesson = final
            v.save(update_fields=["is_final_lesson"])


@author_required
@require_POST
def markdown_preview(request):
    try:
        text = json.loads(request.body).get("markdown", "")
    except ValueError:
        text = ""
    html = md.markdown(text or "", extensions=MD_EXT)
    return JsonResponse({"html": html})


# --- Automated pipeline wizard ---

@author_required
def new_from_video(request):
    if request.method == "POST":
        title = _clean(request.POST.get("title", "").strip())
        if not title:
            messages.error(request, "צריך כותרת")
            return redirect("studio_new_from_video")
        source_type = request.POST.get("source_type", "youtube")
        job = AuthoringJob(
            created_by=request.user, title=title,
            domain=request.POST.get("domain", "matazim"),
            track=request.POST.get("track", ""),
            source_type=source_type,
            source_url=request.POST.get("source_url", "").strip(),
        )
        if source_type == "upload" and request.FILES.get("source_file"):
            job.source_file = request.FILES["source_file"]
        job.save()
        # Kick off background processing (best-effort; worker command is the fallback).
        try:
            from .authoring.pipeline import run_job_async
            run_job_async(job.id)
        except Exception:  # noqa: BLE001
            job.mark(status="pending", step="ממתין לעיבוד (worker)")
        return redirect("studio_job", job_id=job.id)
    return render(request, "app/studio/new_from_video.html", {"domains": _domains_for_form()})


@author_required
def job_status(request, job_id):
    job = get_object_or_404(AuthoringJob, pk=job_id)
    return render(request, "app/studio/job.html", {"job": job})


@author_required
def job_status_api(request, job_id):
    try:
        job = AuthoringJob.objects.get(pk=job_id)
    except AuthoringJob.DoesNotExist:
        raise Http404
    return JsonResponse({
        "status": job.status, "progress": job.progress, "step": job.step,
        "log": job.log[-4000:], "course_slug": job.course.slug if job.course else None,
    })
