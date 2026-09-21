"""The builder: a person's concepts, and resuming the journey (spec §5.0).

Everything here is owner-scoped **in the queryset**, not by a check after the
fetch. That distinction matters: a check can be forgotten on a new view and
fails open; a queryset that only ever contains your own rows cannot hand you
someone else's even by accident.
"""

from django.db.models import Max
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from . import ai
from .access import member_required
from .middleware import language_for
from .models import Concept


def owned(request):
    """The only queryset any view here starts from."""
    return Concept.objects.filter(owner=request.user)


def get_owned_or_404(request, pk):
    return get_object_or_404(owned(request), pk=pk)


@member_required
def concepts(request):
    """The member's concepts. The front door of the gated half."""
    mine = owned(request).select_related("release")
    cap = ai.limits()["concepts_per_member"]
    return render(request, "exo/concepts.html", {
        "concepts": mine,
        # The cap is shown as a state of the page rather than sprung as an
        # error on submit: a form that accepts a title and then refuses it has
        # already wasted the thinking that went into the title.
        "at_cap": mine.count() >= cap,
        "cap": cap,
        "nav": "build",
    })


@member_required
@require_POST
def create(request):
    """A title is all it takes; the journey supplies the rest."""
    title = (request.POST.get("title") or "").strip()
    if not title:
        return redirect("exo:concepts")
    # Spec §8, G5: a ceiling per member. Enforced here and not only in the
    # template, because the template is not the thing an eager retry hits.
    if owned(request).count() >= ai.limits()["concepts_per_member"]:
        return redirect("exo:concepts")
    last = owned(request).aggregate(m=Max("position"))["m"] or 0
    concept = Concept.objects.create(
        owner=request.user,
        title=title[:160],
        language=language_for(request),
        position=last + 1,
    )
    return redirect("exo:concept_resume", pk=concept.pk)


@member_required
def resume(request, pk):
    """Land exactly where this concept was left (spec §5.0, D0.4)."""
    concept = get_owned_or_404(request, pk)
    route = {
        Concept.Stage.INTERVIEW: "exo:concept_interview",
        Concept.Stage.BRAINSTORM: "exo:concept_brainstorm",
        Concept.Stage.OPTIONS: "exo:concept_options",
        Concept.Stage.OUTPUT: "exo:concept_output",
    }.get(concept.stage, "exo:concept_interview")
    return redirect(route, pk=concept.pk)


@member_required
@require_POST
def rename(request, pk):
    concept = get_owned_or_404(request, pk)
    title = (request.POST.get("title") or "").strip()
    if title:
        concept.title = title[:160]
        concept.save(update_fields=["title", "updated_at"])
    return redirect("exo:concepts")


@member_required
@require_POST
def delete(request, pk):
    """Delete the concept and, by cascade, its whole journey."""
    concept = get_owned_or_404(request, pk)
    concept.delete()
    return redirect("exo:concepts")


@member_required
@require_POST
def reorder(request, pk):
    """Move one concept up or down in the owner's list."""
    concept = get_owned_or_404(request, pk)
    direction = request.POST.get("direction")
    ordered = list(owned(request))
    index = next((i for i, c in enumerate(ordered) if c.pk == concept.pk), None)
    if index is None:
        raise Http404
    target = index - 1 if direction == "up" else index + 1
    if 0 <= target < len(ordered):
        ordered[index], ordered[target] = ordered[target], ordered[index]
        for position, item in enumerate(ordered):
            if item.position != position:
                item.position = position
                item.save(update_fields=["position"])
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return JsonResponse({"ok": True})
    return redirect("exo:concepts")


@member_required
@require_POST
def go_back(request, pk):
    """Return to an earlier stage, keeping downstream work but marking it
    stale (spec §5.5). Deletes nothing — that is the whole point."""
    concept = get_owned_or_404(request, pk)
    stage = request.POST.get("stage")
    if stage in Concept.STAGE_ORDER:
        concept.return_to(stage)
    return redirect("exo:concept_resume", pk=concept.pk)
