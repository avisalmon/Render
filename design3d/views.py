"""The pages of design3d (docs/design3d/spec.md)."""

import io
import mimetypes
import re
from datetime import timedelta
from decimal import Decimal, InvalidOperation

from django.contrib import messages as flash
from django.db.models import Count, Q, Sum
from django.http import FileResponse, Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_POST

from . import access, jobs, llm, mail, params, seats, voice
from .forms import AskForm
from .models import PRIVATE, Design, FriendLink, Invite, Maker, Message, Part, Picture, Reference, Settings, Version

MAX_PICTURES = 4


# ---------------------------------------------------------------- the door


def door(request):
    """REQ-D3.1, D3.2: what it is, sign in, ask, wait, or come in. Someone
    who came by a friend's link is let in here once signed in (Chapter 8)."""
    if access.can_enter(request.user):
        return redirect("design3d:designs")
    maker = access.maker_of(request.user)
    friend = Maker.objects.filter(pk=request.session.get(REF_KEY)).first() if request.session.get(REF_KEY) else None
    if (friend is not None and request.user.is_authenticated and (maker is None or maker.pk != friend.pk)
            and (maker is None or maker.status in (Maker.PENDING, Maker.DECLINED))):
        link_pk = request.session.get(REF_LINK)
        if link_pk and not FriendLink.objects.filter(pk=link_pk).filter(
                Q(used_by__isnull=True) | Q(used_by=request.user)).update(used_by=request.user, used_at=timezone.now()):
            # Someone else used this unique link a moment ago.
            request.session.pop(REF_KEY, None)
            request.session.pop(REF_LINK, None)
            flash.error(request, "This invitation link was already used. Ask your friend for a new one.")
            return redirect("design3d:door")
        maker = seats.admit(request.user, friend, request)
        if maker.status == Maker.APPROVED:
            return redirect("design3d:designs")
    return render(request, "design3d/door.html", {"maker": maker, "friend": friend,
                                                  "form": AskForm(initial={"reason": maker.reason if maker else ""})})


REF_KEY = "design3d_ref"
REF_LINK = "design3d_ref_link"
TOUR_KEY = "design3d_tour_seen"
TOUR_STEPS = 7


def welcome(request):
    """The tour (Chapter 8, REQ-D3.74): seven screens, in order, before the
    first design. No skip: every page sends a person here until they finish,
    and "Start designing" counts only after the last screen was seen."""
    if not request.user.is_authenticated:
        return redirect("/design3d/login/?next=/design3d/welcome/")
    if not access.can_enter(request.user):
        return redirect("design3d:door")
    maker = access.maker_of(request.user)
    seen = int(request.session.get(TOUR_KEY) or 0)
    if request.method == "POST":
        if seen < TOUR_STEPS:
            return redirect(f"/design3d/welcome/?step={seen + 1}")
        if maker.tour_done_at is None:
            maker.tour_done_at = timezone.now()
            maker.save(update_fields=["tour_done_at"])
        return redirect("design3d:designs")
    try:
        step = int(request.GET.get("step") or 1)
    except ValueError:
        step = 1
    step = max(1, min(TOUR_STEPS, step, seen + 1))  # one screen at a time, never ahead
    if step > seen:
        request.session[TOUR_KEY] = step
    return render(request, "design3d/welcome.html", {"step": step, "steps": list(range(1, TOUR_STEPS + 1)),
                                                     "turns": maker.turns_left, "section": "welcome"})


def friend_link(request, code):
    """A member's own link (Avi, 2026-10-30): it never runs out; whoever
    comes through it sees who invited them and asks to join as usual (Avi
    approves). The friend is remembered for the points later."""
    fl = FriendLink.objects.filter(code=code).select_related("maker").first()
    if fl is not None:
        if fl.used_by_id is not None and fl.used_by_id != request.user.pk:
            flash.error(request, "This invitation link was already used. Ask your friend for a new one.")
            return redirect("design3d:door")
        if fl.maker.status == Maker.APPROVED:
            request.session[REF_KEY] = fl.maker_id
            request.session[REF_LINK] = fl.pk
        return redirect("design3d:door")
    friend = Maker.objects.filter(ref_code=code, status=Maker.APPROVED).first()  # a link from before 30 Oct
    if friend is not None:
        request.session[REF_KEY] = friend.pk
        request.session.pop(REF_LINK, None)
    return redirect("design3d:door")  # the door lets them in once they are signed in


def _referrer(request, maker=None):
    """Who brought this person, from the link they came through: never
    themselves."""
    pk = request.session.get(REF_KEY)
    friend = Maker.objects.filter(pk=pk).first() if pk else None
    if friend is not None and maker is not None and friend.pk == maker.pk:
        return None
    return friend


@require_POST
def ask(request):
    """Asking to come in, or asking again after a decline."""
    if not request.user.is_authenticated:
        return redirect("design3d:login")
    form = AskForm(request.POST)
    reason = form.cleaned_data["reason"] if form.is_valid() else ""
    maker = access.maker_of(request.user)
    if maker is None:
        maker = Maker.objects.create(user=request.user, display_name=access.display_name_for(request.user), reason=reason,
                                     referred_by=_referrer(request))
        mail.request_notice(maker, request)
    elif maker.status == Maker.DECLINED:
        maker.status, maker.reason, maker.requested_at = Maker.PENDING, reason or maker.reason, timezone.now()
        maker.decided_at = maker.decided_by = None
        maker.save(update_fields=["status", "reason", "requested_at", "decided_at", "decided_by"])
        mail.request_notice(maker, request)
    return redirect("design3d:door")


def invited(request, token):
    """An invitation link (Avi, 2026-10-29): one key, one person. The first
    person to open it signed in is let in and the key is burned; that person
    opening it again just comes in (ownership before validity, methodology
    55); anyone else, or after 14 days or a revoke, is refused."""
    inv = Invite.objects.filter(token=token).first()
    if inv is None:
        raise Http404
    if not request.user.is_authenticated:
        return render(request, "design3d/invited.html", {"inv": inv, "state": "sign_in", "next": request.path})
    if inv.used_by_id == request.user.pk:
        return redirect("design3d:designs")
    if inv.status != "open":
        return render(request, "design3d/invited.html", {"inv": inv, "state": inv.status}, status=410)
    now = timezone.now()
    taken = Invite.objects.filter(pk=inv.pk, used_at__isnull=True, revoked_at__isnull=True,
                                  expires_at__gt=now).update(used_at=now, used_by=request.user)
    if not taken:  # someone else took it a moment ago
        return render(request, "design3d/invited.html", {"inv": inv, "state": "used"}, status=410)
    # Chapter 8: a one-time link is an invitation like a friend's link: 30
    # turns, a seat, or the waiting list.
    maker = seats.admit(request.user, access.maker_of(inv.created_by) if inv.created_by else None, request)
    if maker.status != Maker.APPROVED:
        return redirect("design3d:door")
    flash.success(request, "Welcome to design3d.")
    return redirect("design3d:designs")


# ---------------------------------------------------------------- designs


@access.inside
def designs(request):
    """REQ-D3.10"""
    mine = request.maker.designs.select_related("current").annotate(n=Count("versions"))
    return render(request, "design3d/designs.html", {"designs": mine, "section": "mine",
                                                     "spent": jobs.spent_today(request.maker), "limit": request.maker.limit,
                                                     "friends": _friend_share(request, request.maker)})


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
        "shown_json": _version_json(shown) if shown is not None and shown.status == Version.READY else None,
        "d": d, "shown": shown, "chat": d.messages.prefetch_related("pictures").select_related("version"),
        "versions": d.versions.order_by("-number"),
        "parameters": shown.parameters.all() if shown else [],
        "section": "mine", "stub": llm.stub_mode(), "turns_left": request.maker.turns_left,
        "admin": access.is_admin(request.user) and d.owner_id == request.maker.pk,
        "over": jobs.over_limit(request.maker), "limit": request.maker.limit,
    })


def _clean_reference(upload):
    """An attached STL (Avi, 2026-10-30): read, sized and drawn from three
    sides, or refused with a reason."""
    from . import render

    if upload.size > 25 * 1024 * 1024:
        raise ValueError("The STL is larger than 25 MB.")
    data = upload.read()
    tris = render.read_stl(data)
    if not tris:
        raise ValueError("That STL could not be read. Export it again as an STL (binary or ASCII).")
    if len(tris) > 300_000:
        raise ValueError("The STL is too detailed (more than 300,000 triangles). Simplify it in your slicer or CAD tool.")
    lo, hi = render.bounds(tris)
    name = (upload.name or "reference.stl")[-120:]
    return {"name": name, "data": data, "triangles": len(tris), "size": render.size_mm(tris),
            "bounds": [[round(c, 3) for c in lo], [round(c, 3) for c in hi]], "sheet": render.sheet(data)}


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
    uploads = request.FILES.getlist("pictures")
    stls = [f for f in uploads if f.name.lower().endswith(".stl")][:1]
    files = [f for f in uploads if not f.name.lower().endswith(".stl")][:MAX_PICTURES]
    wants_json = request.headers.get("Accept", "").startswith("application/json")

    def fail(msg, status=400):
        if wants_json:
            return JsonResponse({"error": msg}, status=status)
        flash.error(request, msg)
        return redirect("design3d:design", pk=d.pk)

    if not text and not files and not stls:
        return fail("Write something, or add a picture.")
    if d.messages.filter(state__in=[Message.THINKING, Message.BUILDING]).exists():
        return fail("The last answer is still on its way.", 409)
    if jobs.over_limit(request.maker):
        return fail("You reached today's limit. It resets at midnight.", 429)
    if request.maker.turns_left is not None and request.maker.turns_left <= 0:
        return fail("You have no turns left. Invite a friend: when they join and build their first part, "
                    "you get 30 more.", 402)
    reference = None
    if stls:
        try:
            reference = _clean_reference(stls[0])
        except ValueError as exc:
            return fail(str(exc))
    cleaned = []
    for f in files:
        try:
            cleaned.append(_clean_picture(f, request.user))
        except ValueError as exc:
            return fail(str(exc))
    if not seats.take_turn(request.maker):
        return fail("You have no turns left. Invite a friend: when they join and build their first part, "
                    "you get 30 more.", 402)
    person = Message.objects.create(design=d, role=Message.PERSON, text=text, pin=_pin(request.POST.get("pin")),
                                    cost_usd=voice.cost_of(request.maker, request.POST.getlist("voice")))
    from PIL import Image

    for i, data in enumerate(cleaned):
        with Image.open(io.BytesIO(data)) as img:
            w, h = img.size
        pic = Picture(message=person, width=w, height=h)
        pic.image.save(f"p{i}.jpg", ContentFile(data), save=True)
    if reference is not None:
        ref = Reference(message=person, name=reference["name"], size_mm=reference["size"], triangles=reference["triangles"],
                        bounds=reference["bounds"])
        ref.file.save("reference.stl", ContentFile(reference["data"]), save=False)
        ref.sheet.save("reference.png", ContentFile(reference["sheet"]), save=False)
        ref.save()
    assistant = Message.objects.create(design=d, role=Message.ASSISTANT, state=Message.THINKING)
    d.save(update_fields=["updated_at"])
    jobs.start(assistant)
    if wants_json:
        return JsonResponse({"person": person.pk, "assistant": assistant.pk})
    return redirect("design3d:design", pk=d.pk)


@require_POST
@access.inside
def say(request, pk):
    """The message said out loud: the clip in, the words out, into the
    message box to read and fix before sending (Avi, 2026-10-31)."""
    d = _mine(request, pk)
    if jobs.over_limit(request.maker):
        return JsonResponse({"error": "You reached today's limit. It resets at midnight."}, status=429)
    try:
        text, token = voice.transcribe(request.maker, request.FILES.get("audio"), request.POST.get("seconds"))
    except voice.VoiceError as exc:
        return JsonResponse({"error": str(exc)}, status=400)
    d.save(update_fields=["updated_at"])
    return JsonResponse({"text": text, "token": token})


def _pin(raw):
    """A tapped point from the 3D view, checked: six finite numbers and a
    version number, or None (Avi, 2026-10-29: "mark a part of the 3D view
    to tell the chat to do something here")."""
    import json
    import math

    if not raw:
        return None
    try:
        data = json.loads(raw)
        pin = {k: round(float(data[k]), 2) for k in ("x", "y", "z", "nx", "ny", "nz")}
        pin["version"] = int(data.get("version") or 0)
    except (ValueError, TypeError, KeyError):
        return None
    if not all(math.isfinite(v) and abs(v) < 1e5 for v in pin.values()):
        return None
    part = str(data.get("part") or "")
    if re.match(r"^[a-z][a-z0-9_]{0,39}$", part):  # the tapped part of a several-part design (Chapter 7)
        pin["part"] = part
    return pin


def _message_json(m):
    return {
        "id": m.pk, "role": m.role, "state": m.state, "text": m.text, "assumptions": m.assumptions,
        "step": m.step, "trail": m.trail, "seconds": int((timezone.now() - m.created_at).total_seconds()),
        "version": m.version.number if m.version else None,
        "print": m.version.print_summary if m.version else "",
        "pin": bool(m.pin),
        "pictures": [f"/design3d/files/{p.image.name}" for p in m.pictures.all()],
        "references": [{"name": r.name, "size": r.size_mm} for r in m.references.all()],
    }


def _version_json(v):
    if v is None:
        return None
    return {
        "number": v.number, "status": v.status, "size": v.size_mm, "error": v.error[:500],
        "stl": f"/design3d/files/{v.stl.name}" if v.stl else None,
        "made_by": v.made_by, "checks": v.checks, "fit": v.fit,
        "file_3mf": f"/design3d/d/{v.design_id}/v/{v.number}/3mf/" if v.file_3mf else None,
        "parts": [{"name": p.name, "label": p.label, "count": p.count, "printed": p.printed, "color": p.color,
                   "size": p.size_mm, "checks": p.checks, "stl": f"/design3d/files/{p.stl.name}" if p.stl else None,
                   "download": f"/design3d/d/{v.design_id}/v/{v.number}/part/{p.name}/"} for p in v.parts.all()],
        "parameters": [{"name": p.name, "label": p.label, "value": float(p.value), "min": float(p.minimum),
                        "max": float(p.maximum), "step": float(p.step), "unit": p.unit, "tag": p.tag,
                        "measure": p.needs_measuring, "dim": p.dim} for p in v.parameters.all()],
    }


@access.inside
def poll(request, pk):
    """The state of the chat and the current version, for the page."""
    d = _mine(request, pk)
    jobs.heal(d)
    after = int(request.GET.get("after") or 0)
    msgs = d.messages.filter(Q(pk__gt=after) | Q(state__in=[Message.THINKING, Message.BUILDING])).prefetch_related("pictures").select_related("version")
    pending = d.versions.filter(status=Version.BUILDING).order_by("-number").first()
    request.maker.refresh_from_db(fields=["turns_left"])
    return JsonResponse({"messages": [_message_json(m) for m in msgs], "current": _version_json(jobs.checks_for(d.current)),
                         "title": d.title, "turns_left": request.maker.turns_left, "building": pending.number if pending else None,
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
    measured = set(request.POST.getlist("measured"))
    for p in base.parameters.all():
        raw = request.POST.get(p.name)
        if raw is None:
            continue
        try:
            v = Decimal(raw)
        except InvalidOperation:
            continue
        if not v.is_finite() or v <= 0 and p.minimum > 0:
            continue
        # A size typed in (measured, or edited on the part) may leave the
        # slider's range; one moved on the slider stays inside it.
        typed = p.name in measured or request.POST.get("typed") == p.name
        values[p.name] = v if typed else min(max(v, p.minimum), p.maximum)
    if d.versions.filter(status=Version.BUILDING).exists():
        return JsonResponse({"error": "A build is already running."}, status=409)
    jobs.start_sliders(d, base, params.apply(base.code, values), values, measured)
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
        if request.POST.get("next") == "done":
            return redirect("design3d:done", pk=d.pk)
    elif action == "delete":
        d.delete()
        flash.success(request, "The design was deleted.")
        return redirect("design3d:designs")
    return redirect("design3d:design", pk=d.pk)


@access.inside
def done(request, pk):
    """Avi, 2026-10-29: "Done" beside the chat input opens the finished part
    with what to do with it: download, share, send, and later order a print."""
    d = _mine(request, pk)
    v = jobs.checks_for(d.current)
    if v is None:
        return redirect("design3d:design", pk=d.pk)
    return render(request, "design3d/done.html", {"d": d, "v": v, "section": "mine", "shown_json": _version_json(v)})


@require_POST
@access.inside
def send_files(request, pk):
    """The current part's STL and code to the person's own email."""
    d = _mine(request, pk)
    if d.current is None:
        raise Http404
    ok, said = _mail_result(request, lambda: mail.send_files(d, request.user.email))
    return _said(request, ok, said, redirect("design3d:done", pk=d.pk))


def _mail_result(request, send):
    """(sent, what to tell the person) for an email to their own address."""
    if not request.user.email:
        return False, "Your account has no email address."
    if send():
        return True, f"Sent to {request.user.email}."
    return False, "The email could not be sent. Try again in a minute."


def _said(request, ok, said, page):
    """Answer in place for the page's button (Avi, 2026-10-30: "I have no
    indication that something has been done"), or as a flash after a reload."""
    if request.headers.get("Accept", "").startswith("application/json"):
        return JsonResponse({"ok": ok, "message": said}, status=200 if ok else 502)
    (flash.success if ok else flash.error)(request, said)
    return page


@require_POST
@access.inside
def email_chat(request, pk):
    """Avi, 2026-10-29: "Email me this chat", so the chat can be read and
    replayed off the site (a better model, a better prompt). The admin's own
    designs only, to the admin's own address: another person's chat stays
    theirs."""
    if not access.is_admin(request.user):
        raise Http404
    d = _mine(request, pk)
    ok, said = _mail_result(request, lambda: mail.email_chat(d, request.user.email, request.build_absolute_uri("/").rstrip("/")))
    return _said(request, ok, said, redirect("design3d:design", pk=d.pk))


def analysis_zip(request, token):
    """The zip of chats for analysis, behind a signed link for a day (REQ-D3.75)."""
    from . import analysis

    exp = analysis.from_token(token)
    if exp is None or not exp.file:
        raise Http404
    resp = FileResponse(exp.file.open("rb"), as_attachment=True, filename=f"design3d-analysis-{exp.pk}.zip",
                        content_type="application/zip")
    resp["X-Robots-Tag"] = "noindex"
    resp["Cache-Control"] = "private, no-store"
    return resp


def export(request, token):
    """The page a chat email links to: the chat, every picture sent and every
    version's preview, as one page, for a day. No sign-in: the signed link is
    the key, and only the admin's own designs are ever mailed (REQ-D3.46)."""
    import base64

    d = mail.export_design(token)
    if d is None:
        raise Http404

    def data_uri(field, kind):
        try:
            with field.open("rb") as fh:
                return f"data:{kind};base64," + base64.b64encode(fh.read()).decode()
        except (OSError, ValueError):
            return ""

    pictures = [(f"msg{m.pk}-{n}.jpg", data_uri(p.image, "image/jpeg"))
                for m in d.messages.prefetch_related("pictures") for n, p in enumerate(m.pictures.all(), 1)]
    previews = [(f"v{v.number}.png", data_uri(v.preview, "image/png"))
                for v in d.versions.filter(status=Version.READY).order_by("number") if v.preview]
    response = render(request, "design3d/export.html", {
        "d": d, "text": mail.chat_text(d), "pictures": pictures, "previews": previews,
        "versions": d.versions.order_by("number")})
    response["X-Robots-Tag"] = "noindex"
    response["Cache-Control"] = "private, no-store"
    return response


@access.inside
def download(request, pk, number, kind, part=None):
    """REQ-D3.25: the STL or the OpenSCAD source of a version; for several
    parts (REQ-D3.65) also the 3MF and each part's STL, laid flat."""
    if kind not in ("stl", "scad", "3mf", "part"):
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
    if kind == "3mf":
        if not v.file_3mf:
            raise Http404
        return FileResponse(v.file_3mf.open("rb"), as_attachment=True, filename=f"{stem}-v{v.number}.3mf",
                            content_type="model/3mf")
    if kind == "part":
        p = get_object_or_404(v.parts, name=part)
        f = p.print_stl or p.stl
        return FileResponse(f.open("rb"), as_attachment=True, filename=f"{stem}-v{v.number}-{p.name}.stl",
                            content_type="model/stl")
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


@require_POST
@access.inside
def copy_design(request, pk):
    """Make a copy of a shared design and continue it as your own (spec,
    "planned right after the first release"; Avi, 2026-10-29)."""
    d = get_object_or_404(Design.objects.select_related("owner", "current"), pk=pk, is_shared=True, current__isnull=False)
    if d.current.status != Version.READY:
        raise Http404
    mine = jobs.copy_design(d, request.maker)
    flash.success(request, "Copied. It is yours now.")
    return redirect("design3d:design", pk=mine.pk)


# ---------------------------------------------------------------- Avi's people screen


INVITE_TEXT = ("You're invited to try design3d: a chat that turns a few words, a hand sketch or a photo "
               "into a 3D part you can print. This link works once, just for you: {link}")


def _invites(request):
    """Avi's invitations (2026-10-30): one tap makes a one-time link to send
    however he likes; or withdraw one not used yet."""
    if request.POST["action"] == "revoke":
        Invite.objects.filter(pk=request.POST.get("invite"), used_at__isnull=True).update(revoked_at=timezone.now())
        flash.success(request, "The invitation no longer works.")
        return redirect("design3d:people")
    inv = Invite.objects.create(created_by=request.user, name=(request.POST.get("name") or "").strip()[:80])
    return redirect(f"/design3d/people/?new={inv.pk}#d3-invites")


FRIEND_TEXT = ("{name} invites you to try design3d: a chat that turns a few words, a hand sketch or a photo "
               "into a 3D part you can print. Ask to join here: {link}")


def _friend_share(request, maker):
    """A member's own link and its ready message, and how many joined through it."""
    from urllib.parse import quote

    fresh = FriendLink.objects.create(maker=maker)  # a new link for every send
    link = request.build_absolute_uri(f"/design3d/r/{fresh.code}/")
    text = FRIEND_TEXT.format(name=maker.display_name, link=link)
    joined = maker.referrals.filter(status=Maker.APPROVED).count()
    asked = maker.referrals.count()
    return {"link": link, "text": text, "joined": joined, "asked": asked, "refresh": True,
            "whatsapp": "https://wa.me/?text=" + quote(text),
            "mailto": "mailto:?subject=" + quote("Try design3d") + "&body=" + quote(text)}


@require_POST
@access.inside
def friend_new(request):
    """The next unique link, after one was copied or shared."""
    share = _friend_share(request, request.maker)
    return JsonResponse({k: share[k] for k in ("link", "text", "whatsapp", "mailto")})


def _invite_share(request, inv):
    """The link and the ready message, for the share buttons."""
    from urllib.parse import quote

    link = request.build_absolute_uri(f"/design3d/i/{inv.token}/")
    text = INVITE_TEXT.format(link=link)
    return {"inv": inv, "link": link, "text": text,
            "whatsapp": "https://wa.me/?text=" + quote(text),
            "mailto": "mailto:?subject=" + quote("You're invited to design3d") + "&body=" + quote(text)}


@ensure_csrf_cookie
@access.admin_only
def people(request):
    """REQ-D3.3"""
    if request.method == "POST" and request.POST.get("action") in ("invite", "revoke"):
        return _invites(request)
    if request.method == "POST" and request.POST.get("action") == "export":
        from . import analysis

        export = analysis.send(request)
        flash.success(request, f"Sent: {export.designs} designs, {export.messages} messages, {export.pictures} pictures."
                      if export.sent else "The zip is ready but the mail did not go. Try again in a minute.")
        return redirect("design3d:people")
    if request.method == "POST" and request.POST.get("action") == "seats":
        try:
            limit = max(0, min(10000, int(request.POST.get("seat_limit") or 0)))
        except ValueError:
            flash.error(request, "The seat limit is a whole number.")
            return redirect("design3d:people")
        cfg = Settings.get()
        cfg.seat_limit = limit
        cfg.save(update_fields=["seat_limit"])
        n = seats.fill(request)
        flash.success(request, f"Seat limit {limit}." + (f" {n} waiting {'person is' if n == 1 else 'people are'} in now." if n else ""))
        return redirect("design3d:people")
    if request.method == "POST":
        m = get_object_or_404(Maker, pk=request.POST.get("maker"))
        action = request.POST.get("action")
        if action == "approve":
            sent = access.let_in(m, request.user, request)
            flash.success(request, f"{m.display_name} is in." + (" The welcome email was sent." if sent else ""))
            return redirect("design3d:people")
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
        return redirect("design3d:people")
    start = timezone.localtime().replace(hour=0, minute=0, second=0, microsecond=0)
    makers = Maker.objects.select_related("user", "referred_by").annotate(
        brought=Count("referrals", filter=Q(referrals__status=Maker.APPROVED), distinct=True),
        total=Sum("designs__messages__cost_usd"),
        today=Sum("designs__messages__cost_usd", filter=Q(designs__messages__created_at__gte=start)),
        n_designs=Count("designs", distinct=True))
    groups = {s: [m for m in makers if m.status == s] for s in (Maker.PENDING, Maker.APPROVED, Maker.DECLINED, Maker.WAITING_SEAT)}
    groups["waiting_seat"] = sorted(groups[Maker.WAITING_SEAT], key=lambda m: (m.requested_at, m.pk))
    week = timezone.now() - timedelta(days=7)
    spent = Message.objects.aggregate(all=Sum("cost_usd"), today=Sum("cost_usd", filter=Q(created_at__gte=start)),
                                      week=Sum("cost_usd", filter=Q(created_at__gte=week)))
    seat_info = {"limit": Settings.get().seat_limit, "used": seats.seats_used(), "waiting": len(groups[Maker.WAITING_SEAT])}
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
    invites = Invite.objects.select_related("used_by")[:30]
    fresh = Invite.objects.filter(pk=request.GET.get("new") or 0).first() if (request.GET.get("new") or "").isdigit() else None
    share = _invite_share(request, fresh) if fresh is not None and fresh.status == "open" else None
    return render(request, "design3d/people.html", {"groups": groups, "section": "people", "engine": engine, "invites": invites,
                                                    "seats": seat_info, "spent": spent, "last_export": Settings.get().last_export_at,
                                                    "share": share,
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
        v = Version.objects.filter(Q(stl=path) | Q(preview=path) | Q(file_3mf=path)).select_related("design").first()
        if v is None:
            part = Part.objects.filter(Q(stl=path) | Q(print_stl=path)).select_related("version__design").first()
            v = part.version if part else None
        if not v:
            raise Http404
        if v.design.owner_id != maker.pk and not (v.design.is_shared and v.design.current_id == v.pk):
            raise Http404
    if not PRIVATE.exists(path):
        raise Http404
    ctype = mimetypes.guess_type(path)[0] or ("model/stl" if path.endswith(".stl") else "application/octet-stream")
    resp = FileResponse(open(PRIVATE.path(path), "rb"), content_type=ctype,
                        as_attachment=request.GET.get("download") == "1", filename=path.rsplit("/", 1)[-1])
    resp["Cache-Control"] = "private, max-age=3600"
    return resp
