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

import json
import os
from functools import wraps
from pathlib import Path

from django.conf import settings
from django.core.files.base import ContentFile
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from .models import Course, CourseMaterial, Video


# ---------------------------------------------------------------------------
# Auth helper
# ---------------------------------------------------------------------------

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
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    course_data = data.get("course")
    if not course_data:
        return JsonResponse({"error": "Missing 'course' key"}, status=400)

    slug = course_data.get("slug", "").strip()
    if not slug:
        return JsonResponse({"error": "course.slug is required"}, status=400)

    # --- Upsert Course ---
    course, created = Course.objects.update_or_create(
        slug=slug,
        defaults={
            "title":        course_data.get("title", slug),
            "description":  course_data.get("description", ""),
            "is_published": course_data.get("is_published", False),
        },
    )

    # Handle optional thumbnail (relative path under MEDIA_ROOT)
    thumbnail_rel = course_data.get("thumbnail")
    if thumbnail_rel:
        course.thumbnail = thumbnail_rel
        course.save(update_fields=["thumbnail"])

    # --- Upsert Videos ---
    videos_data = data.get("videos", [])
    video_count = 0
    for vd in videos_data:
        order = vd.get("lesson_order")
        if order is None:
            continue
        Video.objects.update_or_create(
            course=course,
            lesson_order=order,
            defaults={
                "bunny_video_id":  vd.get("bunny_video_id", ""),
                "title":           vd.get("title", f"Lesson {order}"),
                "is_free_preview": vd.get("is_free_preview", False),
                "notes_markdown":  vd.get("notes_markdown", ""),
                "duration_seconds": vd.get("duration_seconds", 0),
            },
        )
        video_count += 1

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
