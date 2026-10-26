"""The pages: the wall (public) and one BKM's page with its conversation
(signed in). docs/bkm/spec.md."""

from django.contrib import messages
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.csrf import ensure_csrf_cookie

from . import access
from .forms import CommentForm
from .models import Bkm, Comment, Like, Star


def _wall_items(user):
    qs = Bkm.objects.all() if access.is_admin(user) else Bkm.objects.filter(is_published=True)
    return qs.annotate(
        n_likes=Count("likes", distinct=True),
        n_comments=Count("comments", filter=Q(comments__deleted_at__isnull=True), distinct=True),
    )


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
    form = CommentForm(request.POST or None)

    if request.method == "POST":
        action = request.POST.get("action", "add")
        if action == "add" and form.is_valid():
            reply_to = None
            if form.cleaned_data.get("reply_to"):
                reply_to = Comment.objects.filter(pk=form.cleaned_data["reply_to"], bkm=bkm).first()
            c = Comment.objects.create(bkm=bkm, author=reader, reply_to=reply_to, body=form.cleaned_data["body"].strip())
            return redirect(f"{request.path}#c{c.pk}")
        if action in ("edit", "delete"):
            c = get_object_or_404(Comment, pk=request.POST.get("comment"), bkm=bkm, deleted_at__isnull=True)
            mine = c.author_id == reader.pk
            if action == "edit" and mine:
                body = (request.POST.get("body") or "").strip()[:2000]
                if body:
                    c.body, c.edited_at = body, timezone.now()
                    c.save(update_fields=["body", "edited_at"])
                return redirect(f"{request.path}#c{c.pk}")
            if action == "delete" and (mine or access.is_admin(request.user)):
                c.deleted_at = timezone.now()
                c.save(update_fields=["deleted_at"])
                messages.success(request, "The comment was deleted.")
                return redirect(f"{request.path}#thread")
            return redirect(request.path)

    comments = list(bkm.comments.select_related("author", "reply_to__author"))
    return render(request, "bkm/bkm.html", {
        "bkm": bkm, "comments": comments, "form": form, "reader": reader,
        "likes": bkm.likes.count(),
        "liked": Like.objects.filter(reader=reader, bkm=bkm).exists(),
        "starred": Star.objects.filter(reader=reader, bkm=bkm).exists(),
        "is_admin": access.is_admin(request.user), "section": "wall",
    })
