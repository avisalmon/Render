"""The pages: the wall of BKMs and the exhibition of projects (public), and
the pages behind them with their conversations (signed in).
docs/bkm/spec.md."""

from django.contrib import messages
from django.db.models import Count, Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.csrf import ensure_csrf_cookie

from . import access
from .forms import BkmForm, CommentForm, ProjectForm
from .models import Bkm, Comment, Like, Project, ProjectComment, ProjectLike, Star


def _wall_items(user):
    qs = Bkm.objects.all() if access.is_admin(user) else Bkm.objects.filter(is_published=True)
    return qs.annotate(
        n_likes=Count("likes", distinct=True),
        n_comments=Count("comments", filter=Q(comments__deleted_at__isnull=True), distinct=True),
    )


def _thread(request, reader, comments, make, path):
    """The conversation under a BKM or a project (REQ-B.15, B.16, B.34):
    add, with a quoted reply; edit your own; delete your own, or any as Avi.
    Answers with a redirect, or None when the request was not about it."""
    if request.method != "POST":
        return None
    action = request.POST.get("action", "add")
    if action == "add":
        form = CommentForm(request.POST)
        if not form.is_valid():
            return None
        reply_to = comments.filter(pk=form.cleaned_data["reply_to"]).first() if form.cleaned_data.get("reply_to") else None
        c = make(author=reader, reply_to=reply_to, body=form.cleaned_data["body"].strip())
        return redirect(f"{path}#c{c.pk}")
    if action in ("edit", "delete"):
        c = get_object_or_404(comments, pk=request.POST.get("comment"), deleted_at__isnull=True)
        mine = c.author_id == reader.pk
        if action == "edit" and mine:
            body = (request.POST.get("body") or "").strip()[:2000]
            if body:
                c.body, c.edited_at = body, timezone.now()
                c.save(update_fields=["body", "edited_at"])
            return redirect(f"{path}#c{c.pk}")
        if action == "delete" and (mine or access.is_admin(request.user)):
            c.deleted_at = timezone.now()
            c.save(update_fields=["deleted_at"])
            messages.success(request, "The comment was deleted.")
            return redirect(f"{path}#thread")
        return redirect(path)
    return None


@ensure_csrf_cookie
def wall(request):
    """REQ-B.1, B.2, B.10: the message on top, then a card per BKM. Anybody
    sees it; only a signed-in person gets the links and the buttons."""
    items = list(_wall_items(request.user))
    reader = access.reader_for(request.user, create=False)
    liked = set(Like.objects.filter(reader=reader).values_list("bkm_id", flat=True)) if reader else set()
    starred = set(Star.objects.filter(reader=reader).values_list("bkm_id", flat=True)) if reader else set()
    only_stars = request.GET.get("starred") == "1" and request.user.is_authenticated
    if only_stars:
        items = [b for b in items if b.pk in starred]
    return render(request, "bkm/wall.html", {
        "items": items, "liked": liked, "starred": starred, "only_stars": only_stars,
        "section": "stars" if only_stars else "wall",
    })


@ensure_csrf_cookie
@access.signed_in
def bkm_page(request, slug):
    """REQ-B.11, B.15, B.16: the card large, how to start, and the thread."""
    qs = Bkm.objects.all() if access.is_admin(request.user) else Bkm.objects.filter(is_published=True)
    bkm = get_object_or_404(qs, slug=slug)
    reader = request.bkm_reader
    done = _thread(request, reader, bkm.comments.all(), lambda **kw: Comment.objects.create(bkm=bkm, **kw), request.path)
    if done:
        return done
    return render(request, "bkm/bkm.html", {
        "bkm": bkm, "comments": list(bkm.comments.select_related("author", "reply_to__author")),
        "form": CommentForm(request.POST or None), "reader": reader,
        "likes": bkm.likes.count(),
        "liked": Like.objects.filter(reader=reader, bkm=bkm).exists(),
        "starred": Star.objects.filter(reader=reader, bkm=bkm).exists(),
        "is_admin": access.is_admin(request.user), "section": "wall", "made": bkm.projects.count(),
    })


@access.signed_in
def bkm_edit(request, slug=None):
    """REQ-B.23: Avi's form for a BKM, every field and the picture. Nobody
    else sees it (404)."""
    if not access.is_admin(request.user):
        raise Http404
    bkm = get_object_or_404(Bkm, slug=slug) if slug else None
    if bkm and request.method == "POST" and request.POST.get("action") == "delete":
        bkm.delete()
        messages.success(request, f"{bkm.name} was removed from the wall.")
        return redirect("bkm:wall")
    form = BkmForm(request.POST or None, request.FILES or None, instance=bkm, user=request.user)
    if request.method == "POST" and form.is_valid():
        b = form.save(commit=False)
        if not bkm and not b.position:
            from django.db.models import Max

            b.position = (Bkm.objects.aggregate(m=Max("position"))["m"] or 0) + 10
        b.save()
        messages.success(request, f"{b.name} is saved.")
        return redirect(f"/bkm/#{b.slug}")
    return render(request, "bkm/bkm_form.html", {"form": form, "bkm": bkm, "section": "wall"})


# ---------------------------------------------------------------- projects


SORTS = {"new": ("Newest", ["-created_at", "-id"]),
         "liked": ("Most liked", ["-n_likes", "-created_at"]),
         "talked": ("Most talked about", ["-n_comments", "-created_at"])}


def search_projects(params):
    """REQ-B.35: plain search and filters over the database, no AI and no
    search engine: words in the title, description, tags or maker's name;
    a BKM, a topic, a kind; and an order."""
    qs = Project.objects.select_related("owner", "bkm").annotate(
        n_likes=Count("likes", distinct=True),
        n_comments=Count("comments", filter=Q(comments__deleted_at__isnull=True), distinct=True),
    )
    for word in (params.get("q") or "").split()[:6]:
        qs = qs.filter(Q(title__icontains=word) | Q(description__icontains=word) | Q(tags__icontains=word)
                       | Q(owner__display_name__icontains=word) | Q(bkm__name__icontains=word))
    if params.get("bkm"):
        qs = qs.filter(bkm__slug=params["bkm"])
    if params.get("topic") in dict(Project.TOPICS):
        qs = qs.filter(topic=params["topic"])
    if params.get("kind") in dict(Project.KINDS):
        qs = qs.filter(kind=params["kind"])
    if params.get("purpose") in dict(Project.PURPOSES):
        qs = qs.filter(purpose=params["purpose"])
    sort = params.get("sort") if params.get("sort") in SORTS else "new"
    return qs.order_by(*SORTS[sort][1]), sort


@ensure_csrf_cookie
def projects(request):
    """REQ-B.30, B.35: the exhibition, public; search and filters on top."""
    items, sort = search_projects(request.GET)
    items = list(items[:200])
    reader = access.reader_for(request.user, create=False)
    liked = set(ProjectLike.objects.filter(reader=reader).values_list("project_id", flat=True)) if reader else set()
    filtering = any(request.GET.get(k) for k in ("q", "bkm", "topic", "kind", "purpose"))
    return render(request, "bkm/projects.html", {
        "items": items, "liked": liked, "sort": sort, "sorts": [(k, v[0]) for k, v in SORTS.items()],
        "bkms": Bkm.objects.filter(is_published=True), "topics": Project.TOPICS, "kinds": Project.KINDS,
        "purposes": Project.PURPOSES, "params": request.GET, "filtering": filtering,
        "total": Project.objects.count(), "section": "projects",
    })


def _may_change(request, project):
    return project.owner.user_id == request.user.pk or access.is_admin(request.user)


@ensure_csrf_cookie
@access.signed_in
def project_page(request, pk):
    """REQ-B.32, B.34: the project large, its links, and its thread."""
    project = get_object_or_404(Project.objects.select_related("owner", "bkm"), pk=pk)
    reader = request.bkm_reader
    done = _thread(request, reader, project.comments.all(),
                   lambda **kw: ProjectComment.objects.create(project=project, **kw), request.path)
    if done:
        return done
    return render(request, "bkm/project.html", {
        "p": project, "comments": list(project.comments.select_related("author", "reply_to__author")),
        "form": CommentForm(request.POST or None), "reader": reader,
        "likes": project.likes.count(), "liked": ProjectLike.objects.filter(reader=reader, project=project).exists(),
        "may_change": _may_change(request, project), "is_admin": access.is_admin(request.user), "section": "projects",
    })


@access.signed_in
def project_edit(request, pk=None):
    """REQ-B.31: pin your own project; change or remove your own (Avi any)."""
    project = get_object_or_404(Project, pk=pk) if pk else None
    if project and not _may_change(request, project):
        raise Http404
    if project and request.method == "POST" and request.POST.get("action") == "delete":
        project.delete()
        messages.success(request, "The project was taken off the exhibition.")
        return redirect("bkm:projects")
    initial = {}
    if not project and request.GET.get("bkm"):
        initial["bkm"] = Bkm.objects.filter(slug=request.GET["bkm"], is_published=True).first()
    form = ProjectForm(request.POST or None, request.FILES or None, instance=project, user=request.user, initial=initial)
    if request.method == "POST" and form.is_valid():
        p = form.save(commit=False)
        if not project:
            p.owner = request.bkm_reader
        if p.kind != Project.IMAGE and not request.FILES.get("image") and p.kind == Project.VIDEO:
            p.image = ""
        p.save()
        return redirect("bkm:project", pk=p.pk)
    return render(request, "bkm/project_form.html", {"form": form, "project": project, "section": "projects"})
