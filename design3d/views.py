"""The pages of design3d (docs/design3d/spec.md)."""

import io
import mimetypes
from decimal import Decimal, InvalidOperation

from django.contrib import messages as flash
from django.db.models import Count, Q, Sum
from django.http import FileResponse, Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_POST

from . import access, jobs, llm, mail, params
from .forms import AskForm
from .models import PRIVATE, Design, Maker, Message, Picture, Version

MAX_PICTURES = 4


# ---------------------------------------------------------------- the door


def door(request):
    """REQ-D3.1, D3.2: what it is, sign in, ask, wait, or come in."""
    if access.can_enter(request.user):
        return redirect("design3d:designs")
    maker = access.maker_of(request.user)
    return render(request, "design3d/door.html", {"maker": maker, "form": AskForm(initial={"reason": maker.reason if maker else ""})})


@require_POST
def ask(request):
    """Asking to come in, or asking again after a decline."""
    if not request.user.is_authenticated:
        return redirect("design3d:login")
    form = AskForm(request.POST)
    reason = form.cleaned_data["reason"] if form.is_valid() else ""
    maker = access.maker_of(request.user)
    if maker is None:
        Maker.objects.create(user=request.user, display_name=access.display_name_for(request.user), reason=reason)
    elif maker.status == Maker.DECLINED:
        maker.status, maker.reason, maker.requested_at = Maker.PENDING, reason or maker.reason, timezone.now()
        maker.decided_at = maker.decided_by = None
        maker.save(update_fields=["status", "reason", "requested_at", "decided_at", "decided_by"])
    return redirect("design3d:door")


# ---------------------------------------------------------------- designs


@access.inside
def designs(request):
    """REQ-D3.10"""
    mine = request.maker.designs.select_related("current").annotate(n=Count("versions"))
    return render(request, "design3d/designs.html", {"designs": mine, "section": "mine",
                                                     "spent": jobs.spent_today(request.maker), "limit": request.maker.limit})


@require_POST
@access.inside
def new_design(request):
    d = Design.objects.create(owner=request.maker)
    return redirect("design3d:design", pk=d.pk)


def _mine(request, pk):
    return get_object_or_404(Design.objects.select_related("current", "owner"), pk=pk, owner=request.maker)


@ensure_csrf_cookie
@access.inside
def design(request, pk):
    """REQ-D3.11: the part, the chat, sizes and versions."""
    d = get_object_or_404(Design.objects.select_related("current", "owner"), pk=pk)
    if d.owner_id != request.maker.pk:
        if d.is_shared:
            return redirect("design3d:shared_design", pk=d.pk)
        raise Http404
    jobs.heal(d)
    shown = d.current
    if request.GET.get("v"):
        shown = d.versions.filter(number=request.GET["v"]).first() or shown
    jobs.checks_for(shown)
    return render(request, "design3d/design.html", {
        "d": d, "shown": shown, "chat": d.messages.prefetch_related("pictures").select_related("version"),
        "versions": d.versions.order_by("-number"),
        "parameters": shown.parameters.all() if shown else [],
        "section": "mine", "stub": llm.stub_mode(),
        "over": jobs.over_limit(request.maker), "limit": request.maker.limit,
    })


def _clean_picture(upload, user):
    """REQ-D3.14: small, no location, checked like every upload."""
    from PIL import Image, ImageOps, UnidentifiedImageError

    if upload.size > 15 * 1024 * 1024:
        raise ValueError("A picture is larger than 15MB.")
    try:
        img = Image.open(upload)
        img.draft("RGB", (2000, 2000))
        img = ImageOps.exif_transpose(img).convert("RGB")
    except (UnidentifiedImageError, OSError, ValueError):
        raise ValueError("That file is not a picture we can read (JPEG, PNG, WebP, HEIC).")
    img.thumbnail((2000, 2000))
    out = io.BytesIO()
    img.save(out, "JPEG", quality=86)
    data = out.getvalue()
    try:
        from app.safety import image_is_safe
    except Exception:  # pragma: no cover
        return data
    ok, _reason = image_is_safe(io.BytesIO(data), user=user, label="design3d picture")
    if not ok:
        raise ValueError("This picture cannot be used here. Please choose another one.")
    return data


@require_POST
@access.inside
def send(request, pk):
    """REQ-D3.12, D3.15: a person's turn; the answer comes in the background."""
    from django.core.files.base import ContentFile

    d = _mine(request, pk)
    text = (request.POST.get("text") or "").strip()[:4000]
    files = request.FILES.getlist("pictures")[:MAX_PICTURES]
    wants_json = request.headers.get("Accept", "").startswith("application/json")

    def fail(msg, status=400):
        if wants_json:
            return JsonResponse({"error": msg}, status=status)
        flash.error(request, msg)
        return redirect("design3d:design", pk=d.pk)

    if not text and not files:
        return fail("Write something, or add a picture.")
    if d.messages.filter(state__in=[Message.THINKING, Message.BUILDING]).exists():
        return fail("The last answer is still on its way.", 409)
    if jobs.over_limit(request.maker):
        return fail("You reached today's limit. It resets at midnight.", 429)
    cleaned = []
    for f in files:
        try:
            cleaned.append(_clean_picture(f, request.user))
        except ValueError as exc:
            return fail(str(exc))
    person = Message.objects.create(design=d, role=Message.PERSON, text=text)
    from PIL import Image

    for i, data in enumerate(cleaned):
        with Image.open(io.BytesIO(data)) as img:
            w, h = img.size
        pic = Picture(message=person, width=w, height=h)
        pic.image.save(f"p{i}.jpg", ContentFile(data), save=True)
    assistant = Message.objects.create(design=d, role=Message.ASSISTANT, state=Message.THINKING)
    d.save(update_fields=["updated_at"])
    jobs.start(assistant)
    if wants_json:
        return JsonResponse({"person": person.pk, "assistant": assistant.pk})
    return redirect("design3d:design", pk=d.pk)


def _message_json(m):
    return {
        "id": m.pk, "role": m.role, "state": m.state, "text": m.text, "assumptions": m.assumptions,
        "step": m.step, "trail": m.trail, "seconds": int((timezone.now() - m.created_at).total_seconds()),
        "version": m.version.number if m.version else None,
        "print": m.version.print_summary if m.version else "",
        "pictures": [f"/design3d/files/{p.image.name}" for p in m.pictures.all()],
    }


def _version_json(v):
    if v is None:
        return None
    return {
        "number": v.number, "status": v.status, "size": v.size_mm, "error": v.error[:500],
        "stl": f"/design3d/files/{v.stl.name}" if v.stl else None,
        "made_by": v.made_by, "checks": v.checks,
        "parameters": [{"name": p.name, "label": p.label, "value": float(p.value), "min": float(p.minimum),
                        "max": float(p.maximum), "step": float(p.step), "unit": p.unit} for p in v.parameters.all()],
    }


@access.inside
def poll(request, pk):
    """The state of the chat and the current version, for the page."""
    d = _mine(request, pk)
    jobs.heal(d)
    after = int(request.GET.get("after") or 0)
    msgs = d.messages.filter(Q(pk__gt=after) | Q(state__in=[Message.THINKING, Message.BUILDING])).prefetch_related("pictures").select_related("version")
    pending = d.versions.filter(status=Version.BUILDING).order_by("-number").first()
    return JsonResponse({"messages": [_message_json(m) for m in msgs], "current": _version_json(jobs.checks_for(d.current)),
                         "title": d.title, "building": pending.number if pending else None,
                         "versions": [{"number": v.number, "status": v.status, "made_by": v.made_by}
                                      for v in d.versions.order_by("-number")]})


@require_POST
@access.inside
def sliders(request, pk):
    """REQ-D3.23: a new version from the sliders, with no call to the model."""
    d = _mine(request, pk)
    base = d.versions.filter(number=request.POST.get("from") or 0).first() or d.current
    if base is None:
        raise Http404
    values = {}
    for p in base.parameters.all():
        raw = request.POST.get(p.name)
        if raw is None:
            continue
        try:
            v = Decimal(raw)
        except InvalidOperation:
            continue
        values[p.name] = min(max(v, p.minimum), p.maximum)
    if d.versions.filter(status=Version.BUILDING).exists():
        return JsonResponse({"error": "A build is already running."}, status=409)
    jobs.start_sliders(d, base, params.apply(base.code, values), values)
    if request.headers.get("Accept", "").startswith("application/json"):
        return JsonResponse({"started": True})
    return redirect("design3d:design", pk=d.pk)


@require_POST
@access.inside
def use_version(request, pk, number):
    """REQ-D3.22: continue from an older version; the newer ones stay."""
    d = _mine(request, pk)
    v = get_object_or_404(d.versions, number=number, status=Version.READY)
    d.current = v
    d.save(update_fields=["current", "updated_at"])
    flash.success(request, f"Continuing from version {v.number}.")
    return redirect("design3d:design", pk=d.pk)


@require_POST
@access.inside
def edit(request, pk):
    d = _mine(request, pk)
    action = request.POST.get("action")
    if action == "rename":
        title = (request.POST.get("title") or "").strip()[:100]
        if title:
            d.title = title
            d.save(update_fields=["title", "updated_at"])
    elif action == "share":
        d.is_shared = request.POST.get("shared") == "1"
        d.shared_at = timezone.now() if d.is_shared else None
        d.save(update_fields=["is_shared", "shared_at", "updated_at"])
        flash.success(request, "Shared with the people in design3d." if d.is_shared else "Private again.")
    elif action == "delete":
        d.delete()
        flash.success(request, "The design was deleted.")
        return redirect("design3d:designs")
    return redirect("design3d:design", pk=d.pk)


@access.inside
def download(request, pk, number, kind):
    """REQ-D3.25: the STL or the OpenSCAD source of a version."""
    if kind not in ("stl", "scad"):
        raise Http404
    d = get_object_or_404(Design, pk=pk)
    mine = d.owner_id == request.maker.pk
    v = get_object_or_404(d.versions, number=number)
    if not mine and not (d.is_shared and d.current_id == v.pk):
        raise Http404
    stem = "".join(c if c.isalnum() else "-" for c in d.title.lower()).strip("-") or "design"
    if kind == "scad":
        if not mine:
            raise Http404
        resp = HttpResponse(v.code, content_type="text/plain; charset=utf-8")
        resp["Content-Disposition"] = f'attachment; filename="{stem}-v{v.number}.scad"'
        return resp
    if not v.stl:
        raise Http404
    return FileResponse(v.stl.open("rb"), as_attachment=True, filename=f"{stem}-v{v.number}.stl", content_type="model/stl")


# ---------------------------------------------------------------- sharing


@access.inside
def shared(request):
    """REQ-D3.31: the gallery of shared designs."""
    items = Design.objects.filter(is_shared=True, current__isnull=False).select_related("owner", "current").order_by("-shared_at")
    return render(request, "design3d/shared.html", {"items": items, "section": "shared"})


@access.inside
def shared_design(request, pk):
    d = get_object_or_404(Design.objects.select_related("owner", "current"), pk=pk, is_shared=True, current__isnull=False)
    return render(request, "design3d/shared_design.html", {"d": d, "v": d.current, "section": "shared"})


# ---------------------------------------------------------------- Avi's people screen


@ensure_csrf_cookie
@access.admin_only
def people(request):
    """REQ-D3.3"""
    if request.method == "POST":
        m = get_object_or_404(Maker, pk=request.POST.get("maker"))
        action = request.POST.get("action")
        if action == "approve":
            m.status = Maker.APPROVED
        elif action in ("decline", "withdraw"):
            m.status = Maker.DECLINED
        elif action == "limit":
            raw = (request.POST.get("limit") or "").strip()
            try:
                m.daily_limit_usd = Decimal(raw) if raw else None
            except InvalidOperation:
                flash.error(request, "A limit is a number of dollars, like 2 or 0.5.")
                return redirect("design3d:people")
            m.save(update_fields=["daily_limit_usd"])
            return redirect("design3d:people")
        m.decided_at, m.decided_by = timezone.now(), request.user
        m.save(update_fields=["status", "decided_at", "decided_by"])
        if m.status == Maker.APPROVED:
            sent = mail.welcome(m, request)
            flash.success(request, f"{m.display_name} is in." + (" The welcome email was sent." if sent else ""))
        return redirect("design3d:people")
    start = timezone.localtime().replace(hour=0, minute=0, second=0, microsecond=0)
    makers = Maker.objects.select_related("user").annotate(
        total=Sum("designs__messages__cost_usd"),
        today=Sum("designs__messages__cost_usd", filter=Q(designs__messages__created_at__gte=start)),
        n_designs=Count("designs", distinct=True))
    groups = {s: [m for m in makers if m.status == s] for s in (Maker.PENDING, Maker.APPROVED, Maker.DECLINED)}
    from django.conf import settings
    from django.db.models import Avg, Max

    from . import builder

    # The engine, for the admin: which OpenSCAD runs and how the last builds went.
    recent = Version.objects.order_by("-created_at")[:50]
    times = Version.objects.filter(pk__in=[v.pk for v in recent], status=Version.READY).aggregate(
        avg=Avg("build_seconds"), max=Max("build_seconds"))
    engine = {"version": builder.engine() or "not installed", "manifold": builder.manifold(),
              "avg": times["avg"], "max": times["max"], "n": len(recent),
              "failed": sum(1 for v in recent if v.status == Version.FAILED)}
    return render(request, "design3d/people.html", {"groups": groups, "section": "people", "engine": engine,
                                                    "default_limit": settings.DESIGN3D_DAILY_LIMIT_USD})


# ---------------------------------------------------------------- files


def file(request, path):
    """Private files, after a check (REQ-D3.41). Pictures: the owner only.
    STLs and previews: the owner, or anyone in when the design is shared
    and it is the current version."""
    if ".." in path or not path.startswith(("pictures/", "stl/", "previews/")):
        raise Http404
    if not access.can_enter(request.user):
        raise Http404
    maker = access.maker_of(request.user)
    if path.startswith("pictures/"):
        pic = Picture.objects.filter(image=path).select_related("message__design").first()
        if not pic or pic.message.design.owner_id != maker.pk:
            raise Http404
    else:
        v = Version.objects.filter(Q(stl=path) | Q(preview=path)).select_related("design").first()
        if not v:
            raise Http404
        if v.design.owner_id != maker.pk and not (v.design.is_shared and v.design.current_id == v.pk):
            raise Http404
    if not PRIVATE.exists(path):
        raise Http404
    ctype = mimetypes.guess_type(path)[0] or ("model/stl" if path.endswith(".stl") else "application/octet-stream")
    resp = FileResponse(open(PRIVATE.path(path), "rb"), content_type=ctype)
    resp["Cache-Control"] = "private, max-age=3600"
    return resp
