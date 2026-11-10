"""The gallery's pages (docs/gallery/spec.md). Likes, stars and comments go
through the REST API (Rule 6); these views render and handle the forms."""

import mimetypes
from pathlib import Path, PurePosixPath

from django.contrib import messages
from django.db.models import Count, Exists, OuterRef, Q, Value
from django.db.models.fields import BooleanField
from django.http import FileResponse, Http404, HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_POST

from . import access, shots, skillpack, skills
from . import skill_chat as chat_engine
from .forms import ExhibitForm, SettingsForm, ShotUploadForm, TrainingForm
from .middleware import COOKIE
from .models import Exhibit, Like, Person, Skill, SkillChat, Star, Topic, Training
from .strings import LANGUAGES, STRINGS, text


def _say(request, key):
    return text(key, getattr(request, "gallery_language", "he"))


def _safe_next(request, default="/gallery/"):
    nxt = request.POST.get("next") or request.GET.get("next") or ""
    if nxt.startswith("/gallery/") and url_has_allowed_host_and_scheme(nxt, allowed_hosts={request.get_host()}):
        return nxt
    return default


def _cards(person, qs):
    """Cards with their counts, and whether the reader liked or starred them.
    Counts are distinct, so a filter on another relation cannot inflate them
    (methodology 20)."""
    qs = qs.select_related("owner").prefetch_related("topics").annotate(
        n_likes=Count("likes", distinct=True),
        n_comments=Count("comments", filter=Q(comments__deleted_at__isnull=True), distinct=True),
    )
    if person is None:
        return qs.annotate(liked=Value(False, output_field=BooleanField()),
                           starred=Value(False, output_field=BooleanField()))
    return qs.annotate(liked=Exists(Like.objects.filter(person=person, exhibit=OuterRef("pk"))),
                       starred=Exists(Star.objects.filter(person=person, exhibit=OuterRef("pk"))))


def search(qs, q="", kind="", topic=""):
    """REQ-G.32: plain database search, no AI. Free text over titles, short
    lines, people's names and topic names in both languages."""
    if kind in (Exhibit.PAGE, Exhibit.SKILL, Exhibit.BKM):
        qs = qs.filter(kind=kind)
    if topic:
        qs = qs.filter(topics__slug=topic)
    for word in q.split()[:8]:
        qs = qs.filter(
            Q(title__icontains=word) | Q(blurb__icontains=word) | Q(url__icontains=word)
            | Q(owner__display_name__icontains=word) | Q(skill__name__icontains=word)
            | Q(topics__name_he__icontains=word) | Q(topics__name_en__icontains=word)
        )
    return qs.distinct()


# ---------------------------------------------------------------- the gallery


NEW_STRIP = 4


def course_for(request, person):
    """Whose course gallery this is (REQ-G.110). A person with a training sees
    theirs by default and the whole gallery by asking (`?scope=all`). Avi sees
    the whole gallery by default and any course by `?course=<id>`. Nobody else
    can open a course that is not theirs."""
    if access.is_admin(request.user):
        wanted = request.GET.get("course", "")
        return Training.objects.filter(pk=wanted).first() if wanted.isdigit() else None
    if person and person.training_id and request.GET.get("scope") != "all":
        return person.training
    return None


def _link(request, **changes):
    """The current address with some parameters changed (None drops one)."""
    params = request.GET.copy()
    for key, value in changes.items():
        if value is None:
            params.pop(key, None)
        else:
            params[key] = value
    query = params.urlencode()
    return request.path + (f"?{query}" if query else "")


@ensure_csrf_cookie
def home(request, skills_tab=False):
    """REQ-G.1, G.32, G.110 to G.113: the board, open to everybody. A course
    member lands on their course's gallery; the newest cards sit on top, the
    rest by likes (or by date, on request); the search hides behind a button.
    The skills tab (REQ-G.40) is the same board with the kind fixed."""
    person = access.person_of(request.user)
    shots.heal()
    q = (request.GET.get("q") or "").strip()[:200]
    kind = Exhibit.SKILL if skills_tab else request.GET.get("kind", "")
    if kind not in (Exhibit.PAGE, Exhibit.SKILL):
        kind = ""
    topic = request.GET.get("topic", "")
    show = request.GET.get("show", "all")
    sort = "new" if request.GET.get("sort") == "new" else "likes"
    course = course_for(request, person)
    base = Exhibit.objects.exclude(kind=Exhibit.BKM)
    if course is not None:
        base = base.filter(owner__training=course)
    if kind:
        base = base.filter(kind=kind)
    qs = search(base, q, "", topic)
    if show == "stars" and person:
        qs = qs.filter(pk__in=Star.objects.filter(person=person).values("exhibit"))
    elif show == "mine" and person:
        qs = qs.filter(owner=person)
    else:
        show = "all"
    searching = bool(q or topic or show != "all" or (kind and not skills_tab))
    cards = _cards(person, qs.select_related("skill"))
    newest = []
    if sort == "likes" and not searching:
        newest = list(_cards(person, base.select_related("skill")).order_by("-created_at", "-id")[:NEW_STRIP])
        cards = cards.exclude(pk__in=[c.pk for c in newest])
    cards = cards.order_by("-n_likes", "-created_at", "-id") if sort == "likes" else cards.order_by("-created_at", "-id")
    return render(request, "gallery/home.html", {
        "cards": cards, "newest": newest, "q": q, "kind": kind, "topic": topic, "show": show, "sort": sort,
        "topics": Topic.objects.all(), "me": person, "section": "skills" if skills_tab else "home",
        "skills_tab": skills_tab, "searching": searching, "course": course,
        "my_course": person.training if person and person.training_id else None,
        "links": {
            "likes": _link(request, sort=None), "new": _link(request, sort="new"),
            "everyone": _link(request, scope="all", course=None), "my_course": _link(request, scope=None, course=None),
            "clear": _link(request, q=None, topic=None, show=None, kind=None),
        },
    })


def skills_home(request):
    return home(request, skills_tab=True)


def skill_guide(request):
    """REQ-G.115: what a skill is and how to write one, before uploading."""
    return render(request, "gallery/skill_guide.html", {"section": "skills"})


@ensure_csrf_cookie
def exhibit(request, pk):
    person = access.person_of(request.user)
    card = get_object_or_404(_cards(person, Exhibit.objects.filter(pk=pk)))
    if card.shot_status == Exhibit.WAITING and card.url:
        shots.heal(limit=1)
        card = get_object_or_404(_cards(person, Exhibit.objects.filter(pk=pk)))
    comments = list(card.comments.select_related("author", "reply_to__author"))
    context = {
        "card": card, "comments": comments, "me": person,
        "section": "skills" if card.kind == Exhibit.SKILL else "home",
        "may_change": bool(person and (card.owner_id == person.pk or person.admin)),
    }
    skill = Skill.objects.filter(exhibit=card).select_related("current").first()
    if skill and skill.current:
        files = list(skill.current.files.all())
        wanted = request.GET.get("file", "SKILL.md")
        shown = next((f for f in files if f.path == wanted), files[0] if files else None)
        context.update(skill=skill, version=skill.current, files=files, shown=shown,
                       updates_left=max(0, Skill.MAX_UPDATES - skill.updates_used))
    return render(request, "gallery/exhibit.html", context)


def skill_download(request, pk, platform):
    """REQ-G.41: anybody, as often as they like; counted."""
    skill = get_object_or_404(Skill.objects.select_related("current", "exhibit"), exhibit_id=pk)
    if platform not in ("claude", "copilot") or skill.current is None:
        raise Http404
    package = skill.current.package_claude if platform == "claude" else skill.current.package_copilot
    skills.count_download(skill)
    name = f"{skill.name}-{'claude-code' if platform == 'claude' else 'copilot'}.zip"
    response = FileResponse(package.open("rb"), content_type="application/zip", as_attachment=True, filename=name)
    response["X-Content-Type-Options"] = "nosniff"
    return response


@access.signed_in
@access.with_training
def skill_new(request, pk=None):
    """REQ-G.50, G.60 to G.62: the first file of a skill chat, or of an update."""
    person = request.gallery_person
    skill = get_object_or_404(Skill.objects.select_related("exhibit"), exhibit_id=pk) if pk else None
    if skill is not None and skill.exhibit.owner_id != person.pk:
        raise Http404
    allowed, why = skills.may_start(person, skill)
    error = ""
    if request.method == "POST" and allowed:
        upload = request.FILES.get("skill")
        if upload is None:
            error = _say(request, "skill.no_file")
        elif upload.size > skillpack.MAX_UPLOAD:
            error = _say(request, "skill.too_big")
        else:
            try:
                chat, _bundle, _found = skills.start(person, upload.name, upload.read(), skill=skill)
            except skillpack.Refused as refused:
                error = _say(request, refused.key) + (f" ({refused.detail})" if refused.detail else "")
            else:
                chat_engine.begin(chat, request.gallery_language)
                return redirect("gallery:skill_chat", pk=chat.pk)
    return render(request, "gallery/skill_new.html", {
        "skill": skill, "allowed": allowed, "why": why, "error": error, "section": "skills",
        "count": skills.published_count(person), "limit": skills.MAX_SKILLS, "me": person,
    })


@ensure_csrf_cookie
@access.signed_in
def skill_chat(request, pk):
    """The upload conversation. Its owner and Avi only."""
    person = request.gallery_person
    chat = get_object_or_404(SkillChat.objects.select_related("person", "skill"), pk=pk)
    if chat.person_id != person.pk and not person.admin:
        raise Http404
    try:
        bundle = skills.bundle_of(chat) if chat.upload else None
    except skillpack.Refused:
        bundle = None
    findings = [line for line in chat.findings.splitlines() if line.strip()]
    return render(request, "gallery/skill_chat.html", {
        "chat": chat, "bundle": bundle, "findings": findings, "chat_messages": chat.messages.all(),
        "section": "skills", "me": person, "notice": n if (n := request.GET.get("n", "")) in STRINGS else "",
        "proposed_topics": chat.proposed_topics.all(),
        "spent_cents": f"{chat.cost_usd * 100:.2f}", "is_owner": chat.person_id == person.pk,
    })


@require_POST
@access.signed_in
def skill_chat_act(request, pk):
    """A button or a sentence in the chat (REQ-G.51 to G.56). Its owner only:
    Avi may read any chat, but only the uploader speaks in it."""
    person = request.gallery_person
    chat = get_object_or_404(SkillChat, pk=pk, person=person)
    action = request.POST.get("action", "")
    upload = None
    if action == "fix":
        f = request.FILES.get("skill")
        if f is None:
            return redirect(f"/gallery/skills/chat/{chat.pk}/?n=skill.no_file")
        if f.size > skillpack.MAX_UPLOAD:
            return redirect(f"/gallery/skills/chat/{chat.pk}/?n=skill.too_big")
        upload = (f.name, f.read())
    problem = chat_engine.act(chat, action, request.gallery_language, upload=upload,
                             reply=request.POST.get("reply", ""))
    chat.refresh_from_db()
    if chat.status == SkillChat.PUBLISHED and chat.skill:
        return redirect("gallery:exhibit", pk=chat.skill.exhibit_id)
    return redirect(f"/gallery/skills/chat/{chat.pk}/" + (f"?n={problem}" if problem else "") + "#gl-chat-end")


@access.signed_in
@access.with_training
def exhibit_new(request):
    """REQ-G.10: hang a page. A BKM card is Avi's alone (REQ-G.80)."""
    person = request.gallery_person
    lang = request.gallery_language
    form = ExhibitForm(request.POST or None, language=lang, admin=person.admin)
    if request.method == "POST" and form.is_valid():
        card = form.save(commit=False)
        card.owner = person
        card.save()
        form.save_m2m()
        shots.take(card)
        return redirect("gallery:exhibit", pk=card.pk)
    return render(request, "gallery/exhibit_form.html", {"form": form, "new": True, "section": "home"})


@access.signed_in
def exhibit_edit(request, pk):
    """REQ-G.12, G.90: the owner changes their own; Avi deletes anything."""
    person = request.gallery_person
    card = get_object_or_404(Exhibit, pk=pk)
    if card.owner_id != person.pk and not person.admin:
        raise Http404
    lang = request.gallery_language
    form = ExhibitForm(request.POST or None, instance=card, language=lang, admin=person.admin)
    upload = ShotUploadForm(language=lang)
    if request.method == "POST":
        action = request.POST.get("action", "save")
        if action == "delete":
            if card.kind == Exhibit.SKILL and hasattr(card, "skill"):
                skills.remove_files(card.skill)
            if card.shot:
                card.shot.delete(save=False)
            card.delete()
            messages.success(request, _say(request, "flash.removed"))
            return redirect("gallery:home")
        if action == "retake":
            card.shot_status, card.shot_tries = Exhibit.WAITING, 0
            card.save(update_fields=["shot_status", "shot_tries"])
            shots.take(card)
            return redirect("gallery:exhibit", pk=card.pk)
        if action == "upload":
            upload = ShotUploadForm(request.POST, request.FILES, language=lang)
            if upload.is_valid():
                if card.shot:
                    card.shot.delete(save=False)
                card.shot.save("upload.jpg", upload.cleaned_data["picture"], save=False)
                card.shot_source, card.shot_status = Exhibit.UPLOAD, Exhibit.OK
                card.shot_taken_at = timezone.now()
                card.save()
                return redirect("gallery:exhibit", pk=card.pk)
        elif form.is_valid():
            changed_url = "url" in form.changed_data
            card = form.save()
            if changed_url:
                card.shot_status, card.shot_tries = Exhibit.WAITING, 0
                card.save(update_fields=["shot_status", "shot_tries"])
                shots.take(card)
            return redirect("gallery:exhibit", pk=card.pk)
    return render(request, "gallery/exhibit_form.html", {
        "form": form, "upload": upload, "card": card, "new": False, "section": "home",
    })


# ---------------------------------------------------------------- people


@ensure_csrf_cookie
def person_page(request, slug):
    """REQ-G.30: everything a person posted. Public; never their training."""
    owner = get_object_or_404(Person, slug=slug)
    me = access.person_of(request.user)
    return render(request, "gallery/person.html", {
        "owner": owner, "cards": _cards(me, owner.exhibits.all()), "me": me,
        "section": "me" if me and me.pk == owner.pk else "home",
    })


@access.signed_in
def settings_page(request):
    """REQ-G.31: name, language and training."""
    person = request.gallery_person
    form = SettingsForm(request.POST or None, instance=person, language=request.gallery_language)
    if request.method == "POST" and form.is_valid():
        person = form.save(commit=False)
        if person.training_id or person.training_other or "training" in form.changed_data:
            person.training_set_at = person.training_set_at or timezone.now()
        person.save()
        messages.success(request, text("flash.saved", person.language))
        response = redirect("gallery:settings")
        response.set_cookie(COOKIE, person.language, max_age=365 * 24 * 3600, samesite="Lax")
        return response
    return render(request, "gallery/settings.html", {"form": form, "me": person, "section": "me"})


@access.signed_in
def training(request):
    """REQ-G.4: asked once, before the first post."""
    person = request.gallery_person
    nxt = _safe_next(request)
    form = TrainingForm(request.POST or None, language=request.gallery_language)
    if request.method == "POST" and form.is_valid():
        choice = form.cleaned_data["training"]
        person.training = None if choice == "other" else form.chosen
        person.training_other = form.cleaned_data.get("other", "").strip() if choice == "other" else ""
        person.training_set_at = timezone.now()
        person.save(update_fields=["training", "training_other", "training_set_at"])
        return redirect(nxt)
    return render(request, "gallery/training.html", {"form": form, "next": nxt, "section": "home"})


# ---------------------------------------------------------------- language


@require_POST
def set_language(request, code):
    """REQ-G.6: remembered on the person's row when signed in, in a cookie
    always (so it also holds after signing out)."""
    if code not in LANGUAGES:
        raise Http404
    if request.user.is_authenticated:
        person = access.ensure_person(request.user, code)
        if person.language != code:
            person.language = code
            person.save(update_fields=["language"])
    response = HttpResponseRedirect(_safe_next(request))
    response.set_cookie(COOKIE, code, max_age=365 * 24 * 3600, samesite="Lax")
    return response


# ---------------------------------------------------------------- files


def file(request, path):
    """Card pictures. Public, like everything else in the gallery, but only
    from the app's own folder and only pictures."""
    clean = PurePosixPath(path)
    if clean.is_absolute() or ".." in clean.parts or len(clean.parts) != 2 or clean.parts[0] != "shots":
        raise Http404
    from .models import FILES

    full = Path(FILES.path(str(clean)))
    if not full.is_file():
        raise Http404
    kind = mimetypes.guess_type(full.name)[0] or ""
    if not kind.startswith("image/"):
        raise Http404
    response = FileResponse(open(full, "rb"), content_type=kind)
    response["Cache-Control"] = "public, max-age=86400"
    response["X-Content-Type-Options"] = "nosniff"
    return response
