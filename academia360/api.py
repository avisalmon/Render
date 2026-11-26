"""The REST API under /academia360/api/ (Rule 6; spec chapter 3).

Every model gets a full CRUD viewset from one factory, so a model added to
models.py without a route fails a test rather than quietly having no API.
Reading is filtered through access.visible (the one circle filter); writing
asks access.may_write; every write lands in the ChangeLog with its actor.
The agent's token (sprint A.3) plugs into the same place: it only changes
who `request.user` is and what `actor_kind` the log records.
"""

from django.apps import apps
from django.db import models as dj_models
from rest_framework import permissions, serializers, viewsets
from rest_framework.exceptions import PermissionDenied

from . import access
from .models import PUBLIC, AgentRun, ChangeLog

# ------------------------------------------------------------- serializers

def serializer_for(model):
    """Every field, read and write; the id and the timestamps read-only."""
    meta = type("Meta", (), {"model": model, "fields": "__all__",
                             "read_only_fields": ("id", "created_at", "updated_at")})
    return type(f"{model.__name__}Serializer", (serializers.ModelSerializer,), {"Meta": meta})


# ------------------------------------------------------------- permissions

class CirclePermission(permissions.BasePermission):
    """Reads: anyone for a public-circle model, a signed-in person otherwise
    (what they then see is filtered by access.visible). Writes: access.may_write."""

    def has_permission(self, request, view):
        model = view.queryset.model
        if request.method in permissions.SAFE_METHODS:
            if access.circle_of(model) == PUBLIC:
                return True
            return bool(request.user and request.user.is_authenticated)
        if request.method == "POST":
            return access.may_write(request.user, model)
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return access.can_see(request.user, obj)
        return access.may_write(request.user, type(obj), obj)


# ----------------------------------------------------------------- logging

def actor_of(request):
    """Who is writing: a person in the app, or the agent through its token
    (A.3 sets request.a360_agent)."""
    user = request.user if getattr(request.user, "is_authenticated", False) else None
    kind = ChangeLog.AGENT if getattr(request, "a360_agent", False) else ChangeLog.PERSON
    run_id = request.headers.get("X-A360-Run") or request.query_params.get("run")
    run = AgentRun.objects.filter(pk=run_id).first() if run_id and str(run_id).isdigit() else None
    reason = (request.headers.get("X-A360-Reason") or "")[:300]
    return user, kind, run, reason


def _text(value):
    if value is None:
        return ""
    if hasattr(value, "pk"):
        return str(value.pk)
    return str(value)


def _snapshot(instance):
    return {f.name: _text(getattr(instance, f.attname if isinstance(f, dj_models.ForeignKey) else f.name))
            for f in instance._meta.concrete_fields if f.name not in ("id", "created_at", "updated_at")}


def log_change(request, instance, before=None, deleted=False):
    user, kind, run, reason = actor_of(request)
    label = instance._meta.label
    common = dict(model=label, row_id=str(instance.pk), by=user, actor_kind=kind, run=run, reason=reason)
    if deleted:
        ChangeLog.objects.create(field="", old="deleted", new="", **common)
    elif before is None:
        ChangeLog.objects.create(field="", old="", new="created", **common)
    else:
        after = _snapshot(instance)
        rows = [ChangeLog(field=k, old=before[k], new=after[k], **common) for k in after if after[k] != before.get(k)]
        ChangeLog.objects.bulk_create(rows)
    if run is not None:
        AgentRun.objects.filter(pk=run.pk).update(rows_touched=dj_models.F("rows_touched") + 1)


# ------------------------------------------------------------------ viewsets

class CircleViewSet(viewsets.ModelViewSet):
    permission_classes = [CirclePermission]

    def get_queryset(self):
        return access.visible(self.queryset.all(), self.request.user)

    def perform_create(self, serializer):
        instance = serializer.save()
        log_change(self.request, instance)

    def perform_update(self, serializer):
        if not access.may_write(self.request.user, type(serializer.instance), serializer.instance):
            raise PermissionDenied
        before = _snapshot(serializer.instance)
        instance = serializer.save()
        log_change(self.request, instance, before=before)

    def perform_destroy(self, instance):
        if not access.may_write(self.request.user, type(instance), instance):
            raise PermissionDenied
        log_change(self.request, instance, deleted=True)
        instance.delete()


def viewset_for(model):
    return type(f"{model.__name__}ViewSet", (CircleViewSet,), {
        "queryset": model._default_manager.all(),
        "serializer_class": serializer_for(model),
        "__doc__": (model.__doc__ or "").strip(),
    })


def route_name(model):
    name = model._meta.model_name
    if name == "criterion":
        return "criteria"
    if name.endswith("y") and not name.endswith("ey"):
        return name[:-1] + "ies"
    if name.endswith("s"):
        return name + "es"
    return name + "s"


# Every model of the app, in one list, built from the registry so nothing is
# left out by hand (a test asserts the API root names each model).
ROUTES = [(route_name(m), viewset_for(m), m) for m in apps.get_app_config("academia360").get_models()]
