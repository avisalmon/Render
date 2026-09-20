"""`/sensorlab/api/schema/` — the API described by the API (Rule 6).

DRF's own OpenAPI generator needs `uritemplate`, which this project does not
carry, and a dependency cannot be added here without Avi running pip. So
this is built from the router registry plus the endpoints that are not
viewsets — which means it cannot go stale the way a hand-written document
does: registering a resource in SL-B2 lists it here with no edit. Swapping
in drf-spectacular later is a change to this file alone.

Not public. A map of the API is for the people building it.
"""

from django.conf import settings
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

CRUD = {
    "list": "GET",
    "create": "POST",
    "retrieve": "GET",
    "update": "PUT",
    "partial_update": "PATCH",
    "destroy": "DELETE",
}

ERROR_SHAPE = (
    "DRF's own shape, adopted rather than re-invented: a refusal is "
    '{"detail": ...}, a validation failure is {field: [messages]}. '
    "A project-wide exception handler would have to be set in shared "
    "settings, which Rule 2 forbids — so the convention is to match what "
    "DRF already does consistently, and to say so here."
)


def describe(router):
    """Every registered resource, straight from the router."""
    resources = []
    for prefix, viewset, _basename in router.registry:
        methods = sorted({verb for name, verb in CRUD.items() if hasattr(viewset, name)})
        serializer = getattr(viewset, "serializer_class", None)
        meta = getattr(serializer, "Meta", None)
        resources.append(
            {
                "path": f"/sensorlab/api/{prefix}/",
                "model": meta.model.__name__ if meta else None,
                "methods": methods,
                "fields": list(getattr(meta, "fields", ())) if meta else [],
                "read_only": list(getattr(meta, "read_only_fields", ())) if meta else [],
                "actions": [fn.url_path for fn in viewset.get_extra_actions()],
            }
        )
    return resources


class SchemaView(APIView):
    def get_permissions(self):
        return [IsAuthenticated()] if settings.DEBUG else [IsAdminUser()]

    def get(self, request):
        from . import router
        from .serializers import SensorLabProfileSerializer

        meta = SensorLabProfileSerializer.Meta
        return Response(
            {
                "title": "SensorLab API",
                "conventions": {
                    "prefix": "/sensorlab/api/",
                    "authentication": ["session, through SensorLab's own sign-in pages"],
                    "pagination": "page number: ?page= and ?page_size=, 25 per page, 100 max",
                    "errors": ERROR_SHAPE,
                },
                "endpoints": [
                    {
                        "path": "/sensorlab/api/profile/me/",
                        "methods": ["GET", "PUT", "PATCH"],
                        "note": "the caller's own profile; `language` is the only writable field",
                        "fields": list(meta.fields),
                        "read_only": list(meta.read_only_fields),
                    },
                    {
                        "path": "/sensorlab/api/labs/<slug>/",
                        "methods": ["GET"],
                        "note": (
                            "The screen endpoint (SL-B2). A GET here does NOT answer in the "
                            "shape `labs/` lists — it returns one lab as spec §3's five steps "
                            "in order, with authored text resolved to one language "
                            "(?language=en|he, defaulting to the caller's profile) and prose "
                            "pre-rendered as `*_html`. Writes to this URL use the authoring "
                            "shape, which is what the author sent. The answer key "
                            "(is_correct, correct_value, tolerance, expected_value, "
                            "pass_tolerance) is omitted for non-staff callers, so grading "
                            "happens server-side."
                        ),
                    },
                    {
                        "path": "/sensorlab/api/attempts/<id>/advance/  ·  /complete/",
                        "methods": ["POST"],
                        "note": (
                            "Progress is a verb, not a field (SL-D3, §9.0 item 2). "
                            "`current_step` and `status` are read-only on the resource, "
                            "because a PATCH that set them would skip the Predict step "
                            "— the one whose value is committing before the data exists. "
                            "`complete/` is refused with 409 unless the attempt is on the "
                            "last step, and the refusal names the step it is actually on."
                        ),
                    },
                    {
                        "path": "/sensorlab/api/attempts/shared/<share_slug>/",
                        "methods": ["GET"],
                        "note": (
                            "The one endpoint an anonymous stranger may open, and only "
                            "when the owner set `is_public`. A private or unknown slug is "
                            "404, never 403 — holding the slug is not permission, and a "
                            "403 would confirm the slug is real. Built by hand rather "
                            "than from the attempt serializer so a field added there "
                            "later cannot publish itself here."
                        ),
                    },
                    {
                        "path": "/sensorlab/api/schema/",
                        "methods": ["GET"],
                        "note": "this document",
                    },
                ],
                "resources": describe(router),
            }
        )
