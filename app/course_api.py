"""
Course Management REST API  (SPR-2.3)
======================================
Secure endpoints for pushing courses from local dev to production.
No DRF required — plain Django JSON views.

Auth: every request must include  Authorization: Bearer <COURSE_MGMT_API_KEY>
      The key is set as a Render env var and in settings_local.py locally.

Endpoints
---------
GET  /api/v1/courses/          — list all courses (verification)
POST /api/v1/courses/sync/     — upsert course + videos + materials (idempotent)
POST /api/v1/media/upload/     — upload a file, returns its stored relative path
"""

import base64
import gzip
import json
from functools import wraps
from pathlib import Path

from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from .models import Course, CourseMaterial, LessonQuiz, Video

# ---------------------------------------------------------------------------
# Auth helper
# ---------------------------------------------------------------------------

def _load_json_body(request):
    """Parse the request body as JSON.

    Supports an optional gzip+base64 encoding when the request carries the header
    ``X-Payload-Encoding: gzip-base64``. This lets the push client send a course's
    code-heavy lesson notes (e.g. a Django/Python course) as opaque bytes so an
    upstream WAF doesn't flag them as an injection attack. The endpoint is already
    protected by the Bearer API key, so accepting an encoded body is safe.
    """
    raw = request.body
    if request.headers.get("X-Payload-Encoding") == "gzip-base64":
        raw = gzip.decompress(base64.b64decode(raw))
    return json.loads(raw)


def require_api_key(view_fn):
    """Decorator — reject requests that don't carry the correct Bearer token."""
    @wraps(view_fn)
    def _wrapper(request, *args, **kwargs):
        expected = getattr(settings, "COURSE_MGMT_API_KEY", "")
        if not expected:
            return JsonResponse({"error": "API key not configured on server"}, status=503)
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return JsonResponse({"error": "Missing Authorization header"}, status=401)
        token = auth_header[len("Bearer "):]
        if token != expected:
            return JsonResponse({"error": "Invalid API key"}, status=403)
        return view_fn(request, *args, **kwargs)
    return _wrapper


# ---------------------------------------------------------------------------
# GET /api/v1/courses/
# ---------------------------------------------------------------------------

@require_api_key
@require_GET
def list_courses(request):
    """Return all courses with basic counts."""
    rows = []
    for c in Course.objects.order_by("title"):
        rows.append({
            "slug": c.slug,
            "title": c.title,
            "is_published": c.is_published,
            "video_count": c.videos.count(),
            "material_count": c.materials.count(),
        })
    return JsonResponse({"courses": rows})


# ---------------------------------------------------------------------------
# POST /api/v1/courses/sync/
# ---------------------------------------------------------------------------

@csrf_exempt
@require_api_key
@require_POST
def sync_course(request):
    """
    Upsert a full course definition.

    Expected JSON body:
    {
        "course": {
            "slug":        "my-course",
            "title":       "...",
            "description": "...",        // optional
            "is_published": true,
            "thumbnail":   "course_thumbnails/my-course.png"  // optional, relative
        },
        "videos": [
            {
                "lesson_order":    1,
                "bunny_video_id":  "abc-123",
                "title":           "...",
                "is_free_preview": false,
                "notes_markdown":  "...",   // optional
                "duration_seconds": 360
            },
            ...
        ],
        "materials": [
            {
                "title":         "...",
                "material_type": "link" | "file",
                "url":           "https://...",   // for link type
                "file_path":     "course_materials/foo.pdf",  // for file type (already uploaded)
                "order":         0
            },
            ...
        ]
    }
    """
    try:
        data = _load_json_body(request)
    except (json.JSONDecodeError, ValueError, OSError):
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    course_data = data.get("course")
    if not course_data:
        return JsonResponse({"error": "Missing 'course' key"}, status=400)

    slug = course_data.get("slug", "").strip()
    if not slug:
        return JsonResponse({"error": "course.slug is required"}, status=400)

    # --- Upsert Course ---
    course_defaults = {
        "title":        course_data.get("title", slug),
        "description":  course_data.get("description", ""),
        "is_published": course_data.get("is_published", False),
    }
    # Only set taxonomy if the client sent it (avoids clobbering on old clients).
    if "domain" in course_data:
        course_defaults["domain"] = course_data["domain"]
    if "track" in course_data:
        course_defaults["track"] = course_data["track"]
    course, created = Course.objects.update_or_create(
        slug=slug,
        defaults=course_defaults,
    )

    # Handle optional thumbnail (relative path under MEDIA_ROOT)
    thumbnail_rel = course_data.get("thumbnail")
    if thumbnail_rel:
        course.thumbnail = thumbnail_rel
        course.save(update_fields=["thumbnail"])

    # --- Upsert Videos ---
    videos_data = data.get("videos", [])
    video_count = 0
    quiz_count = 0
    for vd in videos_data:
        order = vd.get("lesson_order")
        if order is None:
            continue
        video, _ = Video.objects.update_or_create(
            course=course,
            lesson_order=order,
            defaults={
                "bunny_video_id":  vd.get("bunny_video_id", ""),
                "title":           vd.get("title", f"Lesson {order}"),
                "is_free_preview": vd.get("is_free_preview", False),
                "is_final_lesson": vd.get("is_final_lesson", False),
                "notes_markdown":  vd.get("notes_markdown", ""),
                "summary_he":      vd.get("summary_he", ""),
                "reflection_prompt": vd.get("reflection_prompt", ""),
                "duration_seconds": vd.get("duration_seconds", 0),
            },
        )
        video_count += 1

        # Optional per-video quiz
        quiz_data = vd.get("quiz")
        if quiz_data:
            LessonQuiz.objects.update_or_create(
                video=video,
                defaults={
                    "question":         quiz_data.get("question", ""),
                    "options_json":     quiz_data.get("options_json", []),
                    "requires_correct": quiz_data.get("requires_correct", False),
                },
            )
            quiz_count += 1
        else:
            # If push omits a quiz, delete any existing one (kept in sync)
            LessonQuiz.objects.filter(video=video).delete()

    # --- Upsert Materials ---
    materials_data = data.get("materials", [])
    mat_count = 0
    for md in materials_data:
        title = md.get("title", "").strip()
        if not title:
            continue
        defaults = {
            "material_type": md.get("material_type", CourseMaterial.LINK),
            "order":         md.get("order", 0),
            "url":           md.get("url", ""),
        }
        file_path = md.get("file_path", "")
        if file_path:
            defaults["file"] = file_path
        CourseMaterial.objects.update_or_create(
            course=course,
            title=title,
            defaults=defaults,
        )
        mat_count += 1

    return JsonResponse({
        "status": "ok",
        "course_slug": slug,
        "created": created,
        "videos_synced": video_count,
        "quizzes_synced": quiz_count,
        "materials_synced": mat_count,
    })


# ---------------------------------------------------------------------------
# POST /api/v1/media/upload/
# ---------------------------------------------------------------------------

@csrf_exempt
@require_api_key
@require_POST
def upload_media(request):
    """
    Upload a single file to MEDIA_ROOT.

    multipart/form-data fields:
      file      — the file itself
      subdir    — destination subdirectory under MEDIA_ROOT (e.g. "course_materials")
                  Defaults to "course_materials".

    Returns: { "status": "ok", "path": "course_materials/filename.pptx" }
    """
    uploaded = request.FILES.get("file")
    if not uploaded:
        return JsonResponse({"error": "No file attached (field name: 'file')"}, status=400)

    subdir = request.POST.get("subdir", "course_materials").strip("/")

    # Sanitise filename — keep only the basename, no path traversal
    safe_name = Path(uploaded.name).name
    if not safe_name:
        return JsonResponse({"error": "Invalid filename"}, status=400)

    dest_dir = Path(settings.MEDIA_ROOT) / subdir
    dest_dir.mkdir(parents=True, exist_ok=True)

    dest_path = dest_dir / safe_name
    with open(dest_path, "wb") as f:
        for chunk in uploaded.chunks():
            f.write(chunk)

    relative_path = f"{subdir}/{safe_name}"
    return JsonResponse({"status": "ok", "path": relative_path})
