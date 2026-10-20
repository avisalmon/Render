"""Discovery in the API (BK9, Rule 6): my taste (the survey, and what was
derived), recommendations with their reasons, and a book's neighbours."""

from django.shortcuts import get_object_or_404
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .. import discover
from ..access import profile_for
from ..models import CatalogEntry, ProfileTaste
from .permissions import HasBooksProfile


def _me(request):
    return profile_for(request.user)


def _entry(e):
    return {"id": e.pk, "title": e.title, "creators": e.creator_names, "year": e.year}


class DiscoverViewSet(viewsets.ViewSet):
    """GET /discover/ : recommendations, each with its reason.
    GET/POST /discover/taste/ : my survey (likes, dislikes as tag keys).
    GET /discover/entry/?id= : more by the author, readers also read, copies near me."""

    permission_classes = [HasBooksProfile]

    def list(self, request):
        me = _me(request)
        discover.derive(me)
        return Response([{
            **_entry(r["entry"]), "score": r["score"], "near": r["near"],
            "because": _entry(r["because"]) if r["because"] else None,
            "tags": [t.key for t in r["tags"]],
        } for r in discover.for_you(me, limit=int(request.query_params.get("limit") or 24))])

    @action(detail=False, methods=["get", "post"])
    def taste(self, request):
        me = _me(request)
        if request.method == "POST":
            likes = request.data.getlist("like") if hasattr(request.data, "getlist") else request.data.get("like", [])
            dislikes = (request.data.getlist("dislike") if hasattr(request.data, "getlist")
                        else request.data.get("dislike", []))
            discover.set_survey(me, likes, dislikes)
        rows = ProfileTaste.objects.filter(profile=me).select_related("tag")
        return Response([{"tag": t.tag.key, "kind": t.tag.kind, "weight": float(t.weight), "source": t.source}
                         for t in rows])

    @action(detail=False, methods=["get"])
    def entry(self, request):
        me = _me(request)
        e = get_object_or_404(CatalogEntry, pk=request.query_params.get("id") or 0)
        return Response({
            "by_author": [_entry(x) for x in discover.more_by_author(e, me)],
            "also_read": [{**_entry(r["entry"]), "people": r["people"]} for r in discover.also_read(e, me)],
            "near_count": discover.available_near(e, me),
        })
