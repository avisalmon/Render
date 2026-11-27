"""The REST API under /academia360/api/ (Rule 6; spec chapter 3).

Every model gets a full CRUD viewset from one factory, so a model added to
models.py without a route fails a test rather than quietly having no API.
Reading is filtered through access.visible (the one circle filter); writing
asks access.may_write; every write lands in the ChangeLog with its actor.
The agent's token (sprint A.3) plugs into the same place: it only changes
who `request.user` is and what `actor_kind` the log records.
"""

from django.apps import apps
from django.contrib.auth import get_user_model
from django.db import models as dj_models
from django.db import transaction
from rest_framework import authentication, permissions, serializers, status, viewsets
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView

from . import access, people
from .agent_auth import AgentTokenAuthentication
from .models import (
    PUBLIC,
    AgentRun,
    ChangeLog,
    CommitteeAttribute,
    Institution,
    Invitation,
    Role,
    RoleRequest,
)

AUTH = [AgentTokenAuthentication, authentication.SessionAuthentication]

# ------------------------------------------------------------- serializers

def serializer_for(model):
    """Every field, read and write; the id and the timestamps read-only. A
    file in private storage has no URL: the API gives its name, and the
    app's checking view serves it."""
    extra = {}
    for f in model._meta.concrete_fields:
        if isinstance(f, dj_models.FileField) and getattr(f.storage, "base_url", "") is None:
            extra[f.name] = {"use_url": False}
    meta = type("Meta", (), {"model": model, "fields": "__all__",
                             "read_only_fields": ("id", "created_at", "updated_at"), "extra_kwargs": extra})
    return type(f"{model.__name__}Serializer", (serializers.ModelSerializer,), {"Meta": meta})


def _defaults_snapshot(model):
    """What a fresh row looks like, for the chair-only guard on creates."""
    out = {}
    for f in model._meta.concrete_fields:
        if f.name in ("id", "created_at", "updated_at"):
            continue
        default = f.get_default() if f.has_default() else None
        out[f.name] = _text(default)
    return out


# ------------------------------------------------------------- permissions

class CirclePermission(permissions.BasePermission):
    """Reads: anyone for a public-circle model, a signed-in person otherwise
    (what they then see is filtered by access.visible). Writes: access.may_write."""

    def has_permission(self, request, view):
        model = view.queryset.model
        if request.method in permissions.SAFE_METHODS:
            if access.circle_of(model) == PUBLIC or getattr(model, "PUBLIC_Q", None) is not None:
                return True  # what an anonymous reader then gets is filtered by access.visible
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
    params = getattr(request, "query_params", None)
    if params is None:
        params = request.GET  # a page's plain request, not DRF's
    run_id = request.headers.get("X-A360-Run") or params.get("run")
    run = AgentRun.objects.filter(pk=run_id).first() if run_id and str(run_id).isdigit() else None
    reason = (request.headers.get("X-A360-Reason") or "")[:300]
    return user, kind, run, reason


def mail_base(request):
    """Where a mail's link points when the request is a DRF one."""
    from . import mail
    return mail.base_url(getattr(request, "_request", request))


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
    authentication_classes = AUTH
    permission_classes = [CirclePermission]

    def get_queryset(self):
        rows = access.visible(self.queryset.all(), self.request.user)
        # ?field=value on a concrete field narrows the list (the CLI's
        # `list route --q kind=university`, `requests --status open`).
        names = {f.name for f in self.queryset.model._meta.concrete_fields}
        for key, value in self.request.query_params.items():
            if key in names and value != "":
                rows = rows.filter(**{key: value})
        return rows

    def perform_create(self, serializer):
        if serializer.Meta.model is Invitation:
            raise PermissionDenied("an invitation is made through api/admin/invitations/, which mails its link")
        # Saved inside a transaction and checked again with the row, so a
        # leader cannot plant a row in another institution's package: the
        # refusal rolls the insert back.
        with transaction.atomic():
            instance = serializer.save()
            if not access.may_write(self.request.user, type(instance), instance):
                raise PermissionDenied
            touched = access.chair_only_fields_touched(self.request.user, type(instance),
                                                       _defaults_snapshot(type(instance)), _snapshot(instance))
            if touched:
                raise PermissionDenied(f"only a chair sets {sorted(touched)}")
            log_change(self.request, instance)
        if isinstance(instance, RoleRequest):
            people.announce_request(instance)  # a request through the API reaches the admin like any other
        if type(instance).__name__ == "SubmittedFile" and instance.file:
            from . import extract
            extract.extract_row(instance)  # the text is read the moment a file arrives (D2.3)
        if type(instance).__name__ == "Submission" and instance.status == "submitted":
            from . import notify
            notify.submission_arrived(instance, actor=actor_of(self.request)[0], base=mail_base(self.request))  # E.1

    def perform_update(self, serializer):
        if not access.may_write(self.request.user, type(serializer.instance), serializer.instance):
            raise PermissionDenied
        if isinstance(serializer.instance, RoleRequest) and (
                serializer.validated_data.get("status", serializer.instance.status) != serializer.instance.status):
            raise PermissionDenied("a request is decided through api/admin/requests/<pk>/decide/, which grants and mails")
        before = _snapshot(serializer.instance)
        with transaction.atomic():
            instance = serializer.save()
            after = _snapshot(instance)
            touched = access.chair_only_fields_touched(self.request.user, type(instance), before, after)
            if touched:
                raise PermissionDenied(f"only a chair changes {sorted(touched)}")
            if not access.may_write(self.request.user, type(instance), instance):
                raise PermissionDenied  # moved into a package that is not theirs
            log_change(self.request, instance, before=before)
        if type(instance).__name__ == "Submission" and after.get("status") == "submitted" and before.get("status") != "submitted":
            from . import notify
            notify.submission_arrived(instance, actor=actor_of(self.request)[0], base=mail_base(self.request))  # E.1

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
    if name == "analysis":
        return "analyses"
    if name.endswith("y") and not name.endswith("ey"):
        return name[:-1] + "ies"
    if name.endswith("s"):
        return name + "es"
    return name + "s"


# Every model of the app, in one list, built from the registry so nothing is
# left out by hand (a test asserts the API root names each model).
ROUTES = [(route_name(m), viewset_for(m), m) for m in apps.get_app_config("academia360").get_models()]


# -------------------------------------------- the one narrow admin act: roles

class AdminOrAgent(permissions.BasePermission):
    """The admin in a session, or the agent through its token. Nobody else,
    whatever role they hold."""

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and access.is_admin(request.user))


class RoleGrantView(APIView):
    """POST /academia360/api/roles/grant/ with {action, kind, email,
    institution?, title?}: grants or revokes a role (admin, committee,
    leader) or an attribute (chair, reviewer) for an account that already
    exists. It never creates an account and never touches password, staff or
    superuser flags; such keys in the body are ignored. The one admin act the
    agent's token may do (spec 3.4). Everything goes through people.py, so
    the person is mailed like from any other door, and `mailed` in the
    answer is the backend's own count."""

    authentication_classes = AUTH
    permission_classes = [AdminOrAgent]

    KINDS = {"admin": Role.ADMIN, "committee": Role.COMMITTEE_MEMBER, "leader": Role.LEADER,
             "chair": CommitteeAttribute.CHAIR, "reviewer": CommitteeAttribute.REVIEWER}

    def post(self, request):
        data = request.data if isinstance(request.data, dict) else {}
        action = data.get("action", "grant")
        kind = data.get("kind")
        email = (data.get("email") or "").strip()
        if action not in ("grant", "revoke") or kind not in self.KINDS or not email:
            return Response({"detail": "action, kind and email are required"}, status=status.HTTP_400_BAD_REQUEST)
        user = people.find_account(email)
        if user is None:
            return Response({"detail": "no such account; the person signs up first, or use api/admin/invitations/"},
                            status=status.HTTP_404_NOT_FOUND)
        institution = None
        if data.get("institution"):
            institution = Institution.objects.filter(pk=data["institution"]).first()
            if institution is None:
                return Response({"detail": "no such institution"}, status=status.HTTP_404_NOT_FOUND)
        agent = bool(getattr(request, "a360_agent", False))
        reason = (request.headers.get("X-A360-Reason") or "")[:300]
        if kind in ("admin", "committee", "leader"):
            fn = people.grant_role if action == "grant" else people.revoke_role
            kwargs = {"title": data.get("title") or ""} if action == "grant" else {}
            done = fn(request.user, user, self.KINDS[kind], institution=institution, agent=agent, reason=reason, **kwargs)
        else:
            fn = people.set_attribute if action == "grant" else people.clear_attribute
            done = fn(request.user, user, self.KINDS[kind], institution=institution, agent=agent, reason=reason)
        if not done.ok:
            return Response({"detail": done.what}, status=done.status)
        User = get_user_model()
        return Response({"ok": True, "user": user.get_username(), "kind": kind, "action": action, "what": done.what,
                         "mailed": done.mailed, "roles": sorted(access.roles(User.objects.get(pk=user.pk)))})


class RequestDecideView(APIView):
    """POST /academia360/api/admin/requests/<pk>/decide/ with {decision:
    approve|decline, note?}: the chat's way to work the queue. Approving
    grants the role and mails the person; declining mails the note."""

    authentication_classes = AUTH
    permission_classes = [AdminOrAgent]

    def post(self, request, pk):
        row = RoleRequest.objects.filter(pk=pk).select_related("user", "institution").first()
        if row is None:
            return Response({"detail": "no such request"}, status=status.HTTP_404_NOT_FOUND)
        data = request.data if isinstance(request.data, dict) else {}
        decision = data.get("decision")
        if decision not in ("approve", "decline"):
            return Response({"detail": "decision is approve or decline"}, status=status.HTTP_400_BAD_REQUEST)
        done = people.decide_request(request.user, row, decision == "approve", note=data.get("note") or "",
                                     agent=bool(getattr(request, "a360_agent", False)))
        if not done.ok:
            return Response({"detail": done.what}, status=done.status)
        return Response({"ok": True, "request": row.pk, "status": row.status, "what": done.what, "mailed": done.mailed})


class InviteView(APIView):
    """POST /academia360/api/admin/invitations/ with {email, kind,
    institution?, title?}: invites an address with no account (an
    Invitation and its mail), or grants directly when the account exists.
    The only way an Invitation is made: the generic route refuses creates,
    because the token and the mail come from here."""

    authentication_classes = AUTH
    permission_classes = [AdminOrAgent]

    def post(self, request):
        data = request.data if isinstance(request.data, dict) else {}
        kind = RoleGrantView.KINDS.get(data.get("kind") or "")
        if kind not in (Role.ADMIN, Role.COMMITTEE_MEMBER, Role.LEADER):
            return Response({"detail": "kind is admin, committee or leader"}, status=status.HTTP_400_BAD_REQUEST)
        institution = Institution.objects.filter(pk=data.get("institution") or 0).first() if data.get("institution") else None
        done = people.invite(request.user, data.get("email") or "", kind, institution=institution,
                             title=data.get("title") or "", agent=bool(getattr(request, "a360_agent", False)),
                             reason=(request.headers.get("X-A360-Reason") or "")[:300])
        if not done.ok:
            return Response({"detail": done.what}, status=done.status)
        body = {"ok": True, "what": done.what, "mailed": done.mailed, **done.extra}
        if isinstance(done.row, Invitation):
            body["invitation"] = done.row.pk
            body["link"] = people.invitation_link(done.row)
        return Response(body, status=status.HTTP_201_CREATED)


# ------------------------------------------------ extraction (D2.3)

class ExtractView(APIView):
    """GET /academia360/api/admin/extract/: how many submitted files still
    have no text. POST with {limit?}: reads the text out of that many of
    them, where the files are (the server), and answers with a note per
    file. The admin in a session or the agent's token; a member is refused."""

    authentication_classes = AUTH
    permission_classes = [AdminOrAgent]

    def get(self, request):
        from . import extract
        from .models import SubmittedFile
        return Response({"left": extract.missing().count(), "total": SubmittedFile.objects.count(),
                         "with_text": SubmittedFile.objects.exclude(extracted_text="").count()})

    def post(self, request):
        from . import extract
        data = request.data if isinstance(request.data, dict) else {}
        try:
            limit = max(1, min(int(data.get("limit") or 10), 200))
        except (TypeError, ValueError):
            limit = 10
        return Response(extract.extract_missing(limit))


# ------------------------------------------- replication: dev rows to prod

class ReplicateView(APIView):
    """POST /academia360/api/admin/replicate/ with a Django fixture (a JSON
    list of {model, pk, fields}): the day-one way the reference, imported on
    Avi's PC, reaches production, since the reference folder itself never
    leaves the PC (spec 1.5, 3). Token or admin session only. Refuses to
    write into a database that already holds institutions unless `?force=1`,
    so it cannot quietly overwrite later edits in production; after day one,
    rows travel through the ordinary API."""

    authentication_classes = AUTH
    permission_classes = [AdminOrAgent]
    ALLOWED_PREFIX = "academia360."
    NEVER = {"academia360.changelog", "academia360.agentrun", "academia360.accesslog", "academia360.aiconversation",
             "academia360.aimessage", "academia360.aiusage", "academia360.role", "academia360.committeeattribute",
             "academia360.leaderof", "academia360.invitation"}

    def post(self, request):
        from django.core import serializers as dj_serializers

        rows = request.data
        if not isinstance(rows, list):
            return Response({"detail": "a JSON list of fixture objects"}, status=status.HTTP_400_BAD_REQUEST)
        if Institution.objects.exists() and request.query_params.get("force") != "1" \
                and not request.query_params.get("chunk", "").startswith("continue"):
            return Response({"detail": "production already holds institutions; pass ?force=1 to overwrite"},
                            status=status.HTTP_409_CONFLICT)
        bad = [r.get("model") for r in rows if not str(r.get("model", "")).startswith(self.ALLOWED_PREFIX)
               or str(r.get("model", "")).lower() in self.NEVER]
        if bad:
            return Response({"detail": f"not replicable: {sorted(set(bad))}"}, status=status.HTTP_400_BAD_REQUEST)
        import json
        saved = 0
        with transaction.atomic():
            for obj in dj_serializers.deserialize("json", json.dumps(rows), handle_forward_references=True):
                obj.save()
                saved += 1
        return Response({"saved": saved})


class ReplicateFileView(APIView):
    """PUT /academia360/api/admin/replicate/file/<model>/<pk>/ with the raw
    bytes: puts a file into private storage under the name the replicated
    row already carries. Token or admin session only."""

    authentication_classes = AUTH
    permission_classes = [AdminOrAgent]
    MODELS = {"submittedfile": ("academia360", "SubmittedFile", "file"),
              "responseletter": ("academia360", "ResponseLetter", "file")}

    def put(self, request, model, pk):
        from django.core.files.base import ContentFile

        if model not in self.MODELS:
            return Response({"detail": "unknown model"}, status=status.HTTP_404_NOT_FOUND)
        app, name, field = self.MODELS[model]
        row = apps.get_model(app, name).objects.filter(pk=pk).first()
        if row is None:
            return Response({"detail": "no such row; replicate the rows first"}, status=status.HTTP_404_NOT_FOUND)
        target = getattr(row, field).name
        if not target:
            return Response({"detail": "the row carries no file name"}, status=status.HTTP_400_BAD_REQUEST)
        storage = getattr(row, field).storage
        if storage.exists(target) and request.query_params.get("force") != "1":
            return Response({"saved": False, "detail": "already there"})
        if storage.exists(target):
            storage.delete(target)
        saved_name = storage.save(target, ContentFile(request.body))
        if saved_name != target:  # the storage renamed it: keep the row true
            setattr(row, field, saved_name)
            row.save(update_fields=[field])
        return Response({"saved": True, "name": saved_name, "bytes": len(request.body)})
