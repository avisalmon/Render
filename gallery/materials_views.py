"""The materials page (REQ-G.120 to G.126): the shared shelf Avi keeps and
each person's own. Signed-in people only: the shared shelf came from a closed
course's (cohort's) and its documents were never public."""

import mimetypes
from pathlib import Path, PurePosixPath
from urllib.parse import quote

from django import forms
from django.contrib import messages
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.csrf import ensure_csrf_cookie

from . import access, shelves
from .models import FILES, Material, youtube_id
from .strings import text


class MaterialForm(forms.ModelForm):
    class Meta:
        model = Material
        fields = ["kind", "title", "line", "url", "file"]
        widgets = {"url": forms.URLInput(attrs={"dir": "ltr", "inputmode": "url", "placeholder": "https://"})}

    def __init__(self, *args, language="he", **kwargs):
        super().__init__(*args, **kwargs)
        self.language = language
        for name in self.fields:
            self.fields[name].label = text(f"materials.f_{name}", language)
        self.fields["kind"].choices = [(k, text(f"materials.kind_{k}", language)) for k, _ in Material.KINDS]

    def clean(self):
        cleaned = super().clean()
        kind, url, file = cleaned.get("kind"), cleaned.get("url"), cleaned.get("file")
        say = lambda key: text(key, self.language)  # noqa: E731
        if url and not url.lower().startswith(("http://", "https://")):
            self.add_error("url", say("form.need_http"))
        if kind == Material.FILE and not file and not (self.instance and self.instance.file):
            self.add_error("file", say("materials.need_file"))
        if kind in (Material.VIDEO, Material.COURSE, Material.LINK) and not url:
            self.add_error("url", say("materials.need_url"))
        if kind == Material.VIDEO and url and not youtube_id(url):
            self.add_error("url", say("materials.not_youtube"))
        if file and file.size > shelves.FILE_BYTES:
            self.add_error("file", say("materials.file_big"))
        return cleaned


@ensure_csrf_cookie
@access.signed_in
def materials(request):
    person = request.gallery_person
    return render(request, "gallery/materials.html", {
        "shared_items": shelves.shared(), "my_items": shelves.mine(person), "section": "materials",
        "is_admin": person.admin, "space": shelves.total(person), "me": person,
    })


@access.signed_in
def material_edit(request, pk=None):
    person = request.gallery_person
    lang = request.gallery_language
    item = get_object_or_404(shelves.visible(person), pk=pk) if pk else None
    shelf = ("shared" if item.owner_id is None else "mine") if item else request.GET.get("shelf", "shared")
    if shelf not in ("shared", "mine"):
        raise Http404
    if item and not shelves.may_change(person, item):
        raise Http404
    if not item and shelf == "shared" and not person.admin:
        raise Http404
    form = MaterialForm(request.POST or None, request.FILES or None, instance=item, language=lang)
    back = "/gallery/materials/" + ("#mine" if shelf == "mine" else "")
    if request.method == "POST":
        if item and request.POST.get("action") == "delete":
            shelves.remove(item)
            messages.success(request, text("materials.removed", lang))
            return redirect(back)
        if form.is_valid():
            upload = request.FILES.get("file")
            if upload and shelf == "mine":
                try:
                    shelves.check_quota(person, upload.size, but=item)
                except shelves.Refused as why:
                    form.add_error("file", text(str(why), lang))
        if form.is_valid():
            m = form.save(commit=False)
            if not item:
                m.created_by = request.user
                m.owner = person if shelf == "mine" else None
                m.position = shelves.next_position(m.owner)
            if m.kind != Material.FILE and m.file:
                old = m.file.name
                m.file = ""
                m.save()
                if not Material.objects.filter(file=old).exists():
                    FILES.delete(old)
            m.save()
            return redirect(back)
    return render(request, "gallery/material_form.html", {
        "form": form, "item": item, "section": "materials", "shelf": shelf, "back": back,
    })


@access.signed_in
def material_file(request, path):
    """A document, only to someone who can see an item pointing at it."""
    clean = PurePosixPath(path)
    if clean.is_absolute() or ".." in clean.parts or len(clean.parts) != 2 or clean.parts[0] != "materials":
        raise Http404
    if not shelves.file_visible_to(request.gallery_person, str(clean)):
        raise Http404
    full = Path(FILES.path(str(clean)))
    if not full.is_file():
        raise Http404
    kind = mimetypes.guess_type(full.name)[0] or "application/octet-stream"
    # A page or a picture that can carry script never opens on the site's own
    # address: it downloads instead (security sweep habit, methodology 51).
    risky = kind in ("text/html", "application/xhtml+xml", "image/svg+xml", "text/xml", "application/xml") or kind.startswith("text/javascript")
    response = FileResponse(open(full, "rb"), content_type="application/octet-stream" if risky else kind)
    name = quote(full.name.split("-", 1)[-1])
    response["Content-Disposition"] = f"{'attachment' if risky else 'inline'}; filename*=UTF-8''{name}"
    response["Cache-Control"] = "private, max-age=3600"
    response["X-Content-Type-Options"] = "nosniff"
    return response
