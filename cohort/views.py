"""The course site's pages (docs/cohort/spec.md). Likes, stars and comments
go through the REST API (Rule 6); these views render and handle the forms."""

import mimetypes
from pathlib import PurePosixPath

from django.contrib import messages
from django.db.models import Count, Exists, OuterRef, Q
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.csrf import ensure_csrf_cookie

from . import access, mail, shots
from .forms import ExhibitForm, MaterialForm, ShotUploadForm, TrackLinksForm
from .models import Exhibit, Like, Material, Member, Star, Track


# ---------------------------------------------------------------- the door


def door(request):
    """REQ-C.2 to C.5: what a person sees before they are inside."""
    user = request.user
    if access.can_enter(user):
        return redirect("cohort:exhibition")
    member = access.member_of(user)
    if request.method == "POST" and user.is_authenticated:
        if member is None:
            Member.objects.create(user=user, display_name=access.display_name_for(user))
        return redirect("cohort:door")
    if not user.is_authenticated:
        state = "visitor"
    elif member is None:
        state = "ask"
    else:
        state = member.status
    return render(request, "cohort/door.html", {"state": state, "member": member})


# ---------------------------------------------------------------- the exhibition


def _cards(member, qs):
    mine_likes = Like.objects.filter(member=member, exhibit=OuterRef("pk"))
    mine_stars = Star.objects.filter(member=member, exhibit=OuterRef("pk"))
    return (qs.select_related("owner")
            .annotate(n_likes=Count("likes", distinct=True),
                      n_comments=Count("comments", filter=Q(comments__deleted_at__isnull=True), distinct=True),
                      liked=Exists(mine_likes), starred=Exists(mine_stars)))


@ensure_csrf_cookie
@access.inside
def exhibition(request):
    member = request.cohort_member
    shots.heal()
    show = request.GET.get("show", "all")
    qs = Exhibit.objects.all()
    if show == "stars":
        qs = qs.filter(pk__in=Star.objects.filter(member=member).values("exhibit"))
    elif show == "mine":
        qs = qs.filter(owner=member)
    return render(request, "cohort/exhibition.html", {
        "cards": _cards(member, qs), "show": show, "section": "exhibition",
    })


@access.inside
def exhibit_new(request):
    member = request.cohort_member
    form = ExhibitForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        exhibit = form.save(commit=False)
        exhibit.owner = member
        exhibit.save()
        shots.take(exhibit)
        return redirect("cohort:exhibit", pk=exhibit.pk)
    return render(request, "cohort/exhibit_form.html", {"form": form, "section": "exhibition", "new": True})


def _may_change(request, exhibit):
    return exhibit.owner_id == request.cohort_member.pk or request.cohort_member.admin


@ensure_csrf_cookie
@access.inside
def exhibit(request, pk):
    member = request.cohort_member
    card = get_object_or_404(_cards(member, Exhibit.objects.filter(pk=pk)))
    if card.shot_status == Exhibit.WAITING:
        shots.heal(limit=1)
        card.refresh_from_db()
    comments = list(card.comments.select_related("author", "reply_to__author"))
    return render(request, "cohort/exhibit.html", {
        "card": card, "comments": comments, "may_change": _may_change(request, card),
        "section": "exhibition", "me": member,
    })


@access.inside
def exhibit_edit(request, pk):
    exhibit = get_object_or_404(Exhibit, pk=pk)
    if not _may_change(request, exhibit):
        raise Http404
    form = ExhibitForm(request.POST or None, instance=exhibit)
    upload = ShotUploadForm()
    if request.method == "POST":
        action = request.POST.get("action", "save")
        if action == "delete":
            if exhibit.shot:
                exhibit.shot.delete(save=False)
            exhibit.delete()
            messages.success(request, "האתר הוסר מהתערוכה.")
            return redirect("cohort:exhibition")
        if action == "retake":
            exhibit.shot_status, exhibit.shot_tries = Exhibit.WAITING, 0
            exhibit.save(update_fields=["shot_status", "shot_tries"])
            shots.take(exhibit)
            return redirect("cohort:exhibit", pk=exhibit.pk)
        if action == "upload":
            upload = ShotUploadForm(request.POST, request.FILES)
            if upload.is_valid():
                if exhibit.shot:
                    exhibit.shot.delete(save=False)
                exhibit.shot.save("upload.jpg", upload.cleaned_data["picture"], save=False)
                exhibit.shot_source, exhibit.shot_status = Exhibit.UPLOAD, Exhibit.OK
                exhibit.shot_taken_at = timezone.now()
                exhibit.save()
                return redirect("cohort:exhibit", pk=exhibit.pk)
        elif form.is_valid():
            changed_url = "url" in form.changed_data
            exhibit = form.save()
            if changed_url:
                exhibit.shot_status, exhibit.shot_tries = Exhibit.WAITING, 0
                exhibit.save(update_fields=["shot_status", "shot_tries"])
                shots.take(exhibit)
            return redirect("cohort:exhibit", pk=exhibit.pk)
    return render(request, "cohort/exhibit_form.html", {
        "form": form, "upload": upload, "card": exhibit, "section": "exhibition", "new": False,
    })


# ---------------------------------------------------------------- private files


@access.inside
def private_file(request, path):
    """Screenshots and documents, only for people inside (REQ-C.42)."""
    clean = PurePosixPath(path)
    if clean.is_absolute() or ".." in clean.parts or not clean.parts or clean.parts[0] not in ("shots", "materials"):
        raise Http404
    from pathlib import Path

    from .models import PRIVATE

    full = Path(PRIVATE.path(str(clean)))
    if not full.is_file():
        raise Http404
    if clean.parts[0] == "materials":
        from . import shelves

        if not shelves.file_visible_to(request.cohort_member, str(clean)):
            raise Http404
    kind = mimetypes.guess_type(full.name)[0] or "application/octet-stream"
    download = clean.parts[0] == "materials"
    response = FileResponse(open(full, "rb"), content_type=kind, as_attachment=False)
    if download:
        name = full.name.split("-", 1)[-1]
        response["Content-Disposition"] = f"inline; filename*=UTF-8''{name}"
    response["Cache-Control"] = "private, max-age=3600"
    response["X-Content-Type-Options"] = "nosniff"
    return response


# ---------------------------------------------------------------- tracks


@access.inside
def tracks(request):
    return render(request, "cohort/tracks.html", {
        "tracks": Track.objects.select_related("owner"), "section": "tracks",
    })


def _may_edit_track(request, track):
    return (track.owner_id and track.owner_id == request.cohort_member.pk) or request.cohort_member.admin


@access.inside
def track(request, slug):
    t = get_object_or_404(Track.objects.select_related("owner"), slug=slug)
    return render(request, "cohort/track.html", {
        "track": t, "may_edit": _may_edit_track(request, t), "section": "tracks",
        "links": [("vision_url", "מסמך החזון", "לאן המגמה הולכת, ולמה.", t.vision_url),
                  ("graduate_url", "דמות הבוגר", "מה בוגר המגמה יודע, יכול ומביא איתו.", t.graduate_url),
                  ("project_url", "הגדרת הפרויקט", "מה נחשב פרויקט שתלמידים מגישים: הגדרות, דרישות ומכוונים.", t.project_url)],
    })


@access.inside
def track_edit(request, slug):
    t = get_object_or_404(Track, slug=slug)
    if not _may_edit_track(request, t):
        raise Http404
    form = TrackLinksForm(request.POST or None, instance=t)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "הקישורים נשמרו.")
        return redirect("cohort:track", slug=t.slug)
    return render(request, "cohort/track_form.html", {"form": form, "track": t, "section": "tracks"})


# ---------------------------------------------------------------- materials


@ensure_csrf_cookie
@access.inside
def materials(request):
    """Two shelves (REQ-C.30 to C.36): the course's, and the reader's own."""
    from . import shelves

    member = request.cohort_member
    return render(request, "cohort/materials.html", {
        "course_items": shelves.course(), "my_items": shelves.mine(member),
        "section": "materials", "is_admin": member.admin, "space": shelves.total(member),
    })


@access.inside
def material_edit(request, pk=None):
    from . import shelves
    from .models import PRIVATE

    member = request.cohort_member
    item = get_object_or_404(shelves.visible(member), pk=pk) if pk else None
    shelf = ("course" if item.owner_id is None else "mine") if item else request.GET.get("shelf", "course")
    if shelf not in ("course", "mine"):
        raise Http404
    if item and not shelves.may_change(member, item):
        raise Http404
    if not item and shelf == "course" and not member.admin:
        raise Http404
    form = MaterialForm(request.POST or None, request.FILES or None, instance=item)
    back = "/cohort/materials/" + ("#mine" if shelf == "mine" else "")
    if request.method == "POST":
        if item and request.POST.get("action") == "delete":
            shelves.remove(item)
            messages.success(request, "החומר הוסר.")
            return redirect(back)
        if form.is_valid():
            upload = request.FILES.get("file")
            if upload and shelf == "mine":
                try:
                    shelves.check_quota(member, upload.size, but=item)
                except shelves.Refused as why:
                    form.add_error("file", str(why))
        if form.is_valid():
            m = form.save(commit=False)
            if not item:
                m.created_by = request.user
                m.owner = member if shelf == "mine" else None
                m.position = shelves.next_position(m.owner)
            if m.kind != Material.FILE and m.file:
                old = m.file.name
                m.file = ""
                m.save()
                if not Material.objects.filter(file=old).exists():
                    PRIVATE.delete(old)
            m.save()
            return redirect(back)
    return render(request, "cohort/material_form.html", {
        "form": form, "item": item, "section": "materials", "shelf": shelf, "back": back,
    })


# ---------------------------------------------------------------- requests (Avi)


@access.admin_only
def requests_admin(request):
    if request.method == "POST":
        member = get_object_or_404(Member, pk=request.POST.get("member"))
        action = request.POST.get("action")
        if action == "approve":
            member.status = Member.APPROVED
        elif action in ("decline", "withdraw"):
            member.status = Member.DECLINED
        member.decided_at = timezone.now()
        member.decided_by = request.user
        member.save(update_fields=["status", "decided_at", "decided_by"])
        if action == "approve":
            sent = mail.welcome(member, request)
            messages.success(request, f"{member.display_name} אושר/ה" + (", ונשלח מייל." if sent else "."))
        return redirect("cohort:requests")
    people = Member.objects.select_related("user").order_by("-requested_at")
    return render(request, "cohort/requests.html", {
        "pending": [m for m in people if m.status == Member.PENDING],
        "approved": [m for m in people if m.status == Member.APPROVED],
        "declined": [m for m in people if m.status == Member.DECLINED],
        "section": "requests",
    })


@access.inside
def project_example(request):
    """Avi's example project definition for the imaginary electronics track
    (2026-10-21): a document page of its own, for participants only. Avi links
    it from the track's "project definition"."""
    return render(request, "cohort/project_example.html")
