"""/memz/api/schema/: the API described by the API (spec §12.3).

DRF's own OpenAPI generator needs `uritemplate`, which this project does
not carry, and adding a package for a document is the wrong trade for a
skeleton sprint. This lists every registered resource, its verbs and its
extra actions, straight from the router, so it cannot go stale. Staff only
in production (spec Rule 12.3.3.9); a member gets a 403, not a map.
Swapping in drf-spectacular later is a one-line change here.
"""

from django.conf import settings
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.renderers import JSONRenderer
from rest_framework.response import Response
from rest_framework.views import APIView

from .renderers import StaffOnlyBrowsableRenderer

CRUD = ["list", "create", "retrieve", "update", "partial_update", "destroy"]


def describe(router):
    resources = []
    for prefix, viewset, _basename in router.registry:
        allowed = getattr(viewset, "http_method_names", [])
        verbs = [
            verb for verb in CRUD
            if hasattr(viewset, verb) and (
                verb in ("list", "retrieve") and "get" in allowed
                or verb == "create" and "post" in allowed
                or verb == "update" and "put" in allowed
                or verb == "partial_update" and "patch" in allowed
                or verb == "destroy" and "delete" in allowed
            )
        ]
        actions = [
            {"name": fn.url_path, "methods": sorted(fn.mapping), "detail": fn.detail}
            for fn in viewset.get_extra_actions()
        ]
        model = viewset.serializer_class.Meta.model
        resources.append({
            "prefix": prefix,
            "path": f"/memz/api/{prefix}/",
            "model": model.__name__,
            "verbs": verbs,
            "actions": [a["name"] for a in actions],
            "action_details": actions,
            "fields": list(viewset.serializer_class.Meta.fields),
            "read_only": list(getattr(viewset.serializer_class.Meta, "read_only_fields", ())),
        })
    return resources


class SchemaView(APIView):
    renderer_classes = [JSONRenderer, StaffOnlyBrowsableRenderer]

    def get_permissions(self):
        return [IsAuthenticated()] if settings.DEBUG else [IsAdminUser()]

    def get(self, request):
        from . import router

        return Response({
            "title": "memz API",
            "resources": describe(router),
            "other": [
                {"path": "/memz/api/profile/", "methods": ["GET", "PATCH"], "note": "the caller's own profile"},
                {"path": "/memz/api/schema/", "methods": ["GET"], "note": "this document"},
            ],
            "authentication": ["session (browser)", "X-Memz-Player token (game actions, from SPR-Z.3)"],
        })
