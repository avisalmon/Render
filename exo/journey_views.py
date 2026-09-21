"""The four stages of the journey (spec §5.1 - §5.4).

Every stage follows the same discipline: read rows, call `exo.ai` once, write
rows. A provider failure leaves the previous state untouched and the page
offers a retry — there is no in-memory journey state to lose (spec §8, G7).
"""

import json

from django.db.models import Max
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from . import ai
from .access import member_required
from .concept_views import get_owned_or_404
from .models import (
    BrainstormEntry,
    Concept,
    ExoAttribute,
    GeneratedOption,
    InterviewMessage,
    NewspaperStyle,
    PressRelease,
)

# ---------------------------------------------------------------------------
# shared
# ---------------------------------------------------------------------------


def _stage_context(concept):
    """What the progress rail needs, computed once (spec §5.5, D5.1)."""
    return {
        "concept": concept,
        "stages": [
            {"key": s, "index": i, "reached": concept.has_reached(s),
             "current": concept.stage == s}
            for i, s in enumerate(Concept.STAGE_ORDER)
        ],
    }


def _error(message, status=400):
    return JsonResponse({"detail": message}, status=status)


def _ai_failed(exc):
    """One place that turns an AI failure into something a page can show."""
    if isinstance(exc, ai.AiLimit):
        return _error("limit", status=429)
    return _error("ai", status=503)


# ---------------------------------------------------------------------------
# stage 1 — the interview
# ---------------------------------------------------------------------------


@member_required
def interview(request, pk):
    concept = get_owned_or_404(request, pk)
    messages = list(concept.messages.all())
    if not messages:
        # The assistant opens, so the page is never an empty box waiting for a
        # person who does not know what is expected of them.
        opening = ai.interview_reply(concept, [], concept.language, user=request.user)
        InterviewMessage.objects.create(
            concept=concept, role=InterviewMessage.Role.ASSISTANT,
            content=opening, order=0,
        )
        messages = list(concept.messages.all())
    context = _stage_context(concept)
    context.update({"messages": messages, "is_stub": ai.is_stub(), "nav": "build"})
    return render(request, "exo/interview.html", context)


@member_required
@require_POST
def interview_send(request, pk):
    """One user turn, then one assistant turn. The user's turn is written
    BEFORE the provider is called, so an outage cannot swallow what they
    typed."""
    concept = get_owned_or_404(request, pk)
    try:
        text = (json.loads(request.body or "{}").get("text") or "").strip()
    except json.JSONDecodeError:
        return _error("bad request")
    if not text:
        return _error("empty")

    order = (concept.messages.aggregate(m=Max("order"))["m"] or 0) + 1
    InterviewMessage.objects.create(
        concept=concept, role=InterviewMessage.Role.USER,
        content=text, order=order,
    )
    try:
        reply = ai.interview_reply(
            concept, list(concept.messages.all()), concept.language,
            user=request.user,
        )
    except ai.AiError as exc:
        return _ai_failed(exc)

    message = InterviewMessage.objects.create(
        concept=concept, role=InterviewMessage.Role.ASSISTANT,
        content=reply, order=order + 1,
    )
    return JsonResponse({"reply": message.content})


@member_required
@require_POST
def interview_summary(request, pk):
    """Ask the model for the settled summary, for the user to edit."""
    concept = get_owned_or_404(request, pk)
    try:
        return JsonResponse(ai.settle(
            concept, list(concept.messages.all()), concept.language,
            user=request.user,
        ))
    except ai.AiError as exc:
        return _ai_failed(exc)


@member_required
@require_POST
def settle(request, pk):
    """Accept the summary (as edited) and move to the brainstorm."""
    concept = get_owned_or_404(request, pk)
    try:
        data = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return _error("bad request")
    concept.mtp = (data.get("mtp") or "").strip()
    concept.special = (data.get("special") or "").strip()
    concept.unique = (data.get("unique") or "").strip()
    concept.save(update_fields=["mtp", "special", "unique", "updated_at"])
    concept.advance_to(Concept.Stage.BRAINSTORM)
    return JsonResponse({"ok": True, "next": f"/exo/concepts/{concept.pk}/brainstorm/"})


# ---------------------------------------------------------------------------
# stage 2 — the brainstorm
# ---------------------------------------------------------------------------


@member_required
def brainstorm(request, pk):
    concept = get_owned_or_404(request, pk)
    attributes = list(ExoAttribute.objects.all())
    entries = {}
    for entry in concept.entries.select_related("attribute"):
        entries.setdefault(entry.attribute_id, []).append(entry)
    slots = [{"attribute": a, "entries": entries.get(a.id, [])} for a in attributes]
    context = _stage_context(concept)
    context.update({
        "slots": slots,
        "filled": sum(1 for s in slots if s["entries"]),
        "total": len(slots),
        "nav": "build",
    })
    return render(request, "exo/brainstorm.html", context)


@member_required
@require_POST
def entry_add(request, pk):
    concept = get_owned_or_404(request, pk)
    try:
        data = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return _error("bad request")
    text = (data.get("text") or "").strip()
    attribute = ExoAttribute.objects.filter(key=data.get("attribute")).first()
    if not text or attribute is None:
        return _error("empty")
    entry = BrainstormEntry.objects.create(
        concept=concept, attribute=attribute, text=text,
    )
    return JsonResponse({"id": entry.id, "text": entry.text})


@member_required
@require_POST
def entry_edit(request, pk, entry_id):
    concept = get_owned_or_404(request, pk)
    entry = concept.entries.filter(pk=entry_id).first()
    if entry is None:
        return _error("not found", status=404)
    try:
        data = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return _error("bad request")
    text = (data.get("text") or "").strip()
    if not text:
        return _error("empty")
    entry.text = text
    entry.save(update_fields=["text"])
    return JsonResponse({"id": entry.id, "text": entry.text})


@member_required
@require_POST
def entry_delete(request, pk, entry_id):
    concept = get_owned_or_404(request, pk)
    deleted, _ = concept.entries.filter(pk=entry_id).delete()
    if not deleted:
        return _error("not found", status=404)
    return JsonResponse({"ok": True})


@member_required
@require_POST
def to_options(request, pk):
    concept = get_owned_or_404(request, pk)
    concept.advance_to(Concept.Stage.OPTIONS)
    return redirect("exo:concept_options", pk=concept.pk)


# ---------------------------------------------------------------------------
# stage 3 — options and selection
# ---------------------------------------------------------------------------


@member_required
def options(request, pk):
    concept = get_owned_or_404(request, pk)
    attributes = list(ExoAttribute.objects.all())
    by_attribute, entries = {}, {}
    for option in concept.options.select_related("attribute"):
        by_attribute.setdefault(option.attribute_id, []).append(option)
    for entry in concept.entries.select_related("attribute"):
        entries.setdefault(entry.attribute_id, []).append(entry)
    slots = [{
        "attribute": a,
        "options": by_attribute.get(a.id, []),
        "entries": entries.get(a.id, []),
        "selected": sum(1 for o in by_attribute.get(a.id, []) if o.is_selected),
    } for a in attributes]
    context = _stage_context(concept)
    context.update({
        "slots": slots,
        "with_selection": sum(1 for s in slots if s["selected"]),
        "total": len(slots),
        "is_stub": ai.is_stub(),
        "nav": "build",
    })
    return render(request, "exo/options.html", context)


@member_required
@require_POST
def options_generate(request, pk):
    """Generate for ONE attribute. Per-slot on purpose (spec §5.3, D3.4): a
    phone user sees each slot arrive, and one slot's failure is one slot's
    failure rather than the whole stage's."""
    concept = get_owned_or_404(request, pk)
    try:
        data = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return _error("bad request")
    attribute = ExoAttribute.objects.filter(key=data.get("attribute")).first()
    if attribute is None:
        return _error("not found", status=404)

    existing = concept.options.filter(attribute=attribute)
    keep = list(existing.filter(is_selected=True)) + list(
        existing.filter(is_user_authored=True).exclude(is_selected=True)
    )
    entries = list(concept.entries.filter(attribute=attribute))
    try:
        produced = ai.generate_options(
            concept, attribute, entries, concept.language, user=request.user,
        )
    except ai.AiError as exc:
        return _ai_failed(exc)

    # Only now, with new content in hand, remove the replaceable ones. A
    # failure above must not leave the slot empty.
    existing.exclude(pk__in=[o.pk for o in keep]).delete()
    start = len(keep)
    made = [
        GeneratedOption.objects.create(
            concept=concept, attribute=attribute,
            content=item["content"], research_note=item["research_note"],
            order=start + i,
        )
        for i, item in enumerate(produced)
    ]
    return JsonResponse({"options": [
        {"id": o.id, "content": o.content, "research_note": o.research_note,
         "is_selected": o.is_selected, "is_user_authored": o.is_user_authored}
        for o in list(keep) + made
    ]})


@member_required
@require_POST
def option_select(request, pk, option_id):
    concept = get_owned_or_404(request, pk)
    option = concept.options.filter(pk=option_id).first()
    if option is None:
        return _error("not found", status=404)
    option.is_selected = not option.is_selected
    option.save(update_fields=["is_selected"])
    return JsonResponse({"id": option.id, "is_selected": option.is_selected})


@member_required
@require_POST
def option_add_own(request, pk):
    """The user's own option. Never replaced by a regenerate."""
    concept = get_owned_or_404(request, pk)
    try:
        data = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return _error("bad request")
    attribute = ExoAttribute.objects.filter(key=data.get("attribute")).first()
    text = (data.get("text") or "").strip()
    if attribute is None or not text:
        return _error("empty")
    order = (concept.options.filter(attribute=attribute)
             .aggregate(m=Max("order"))["m"] or 0) + 1
    option = GeneratedOption.objects.create(
        concept=concept, attribute=attribute, content=text,
        is_user_authored=True, is_selected=True, order=order,
    )
    return JsonResponse({
        "id": option.id, "content": option.content, "research_note": "",
        "is_selected": True, "is_user_authored": True,
    })


@member_required
@require_POST
def to_output(request, pk):
    concept = get_owned_or_404(request, pk)
    concept.advance_to(Concept.Stage.OUTPUT)
    return redirect("exo:concept_output", pk=concept.pk)


# ---------------------------------------------------------------------------
# stage 4 — the document and the press release
# ---------------------------------------------------------------------------


def _selections(concept):
    """What the user chose, grouped by attribute, in framework order."""
    grouped = {}
    for option in (concept.options.filter(is_selected=True)
                   .select_related("attribute")):
        grouped.setdefault(option.attribute, []).append(option.content)
    return sorted(grouped.items(), key=lambda kv: (kv[0].category, kv[0].order))


@member_required
def output(request, pk):
    concept = get_owned_or_404(request, pk)
    release = getattr(concept, "release", None)
    context = _stage_context(concept)
    context.update({
        "release": release,
        # (value, label key, blurb key) — the template should not hold a second
        # copy of the visibility vocabulary.
        "vis_choices": [
            ("public", "vis.public", "vis.public_blurb"),
            ("timed", "vis.timed", "vis.timed_blurb"),
            ("specific", "vis.specific", "vis.specific_blurb"),
            ("private", "vis.private", "vis.private_blurb"),
        ],
        "styles": NewspaperStyle.objects.filter(is_active=True),
        "selections": _selections(concept),
        "is_stub": ai.is_stub(),
        "now": timezone.now(),
        "nav": "build",
    })
    return render(request, "exo/output.html", context)


def _screen_before_the_wall(release, user):
    """Spec §8, G6: nothing reaches the public wall unscreened.

    Returns "" when the release may stay public, or a reason when it may not —
    in which case it has already been made private, since a refusal that leaves
    the text visible would be theatre.

    Private and specific-people releases are never screened. What a person
    writes for themselves, or hands to three named people, is not the museum's
    business, and sending it to a provider anyway would be a small betrayal of
    a person who deliberately chose not to publish.
    """
    public_choices = (PressRelease.Visibility.PUBLIC, PressRelease.Visibility.TIMED)
    if release.visibility not in public_choices:
        return ""
    parts = [release.headline, release.body, release.document_body]
    text = "\n\n".join(part for part in parts if part)
    ok, detail = ai.public_text_is_safe(text, user=user)
    if ok:
        return ""
    release.visibility = PressRelease.Visibility.PRIVATE
    release.public_until = None
    release.save(update_fields=["visibility", "public_until", "updated_at"])
    return detail or "flagged"


@member_required
@require_POST
def output_generate(request, pk):
    """Write both artifacts. Refuses to silently overwrite a hand edit."""
    concept = get_owned_or_404(request, pk)
    release = getattr(concept, "release", None)
    try:
        data = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        data = {}
    if release and release.edited_by_owner and not data.get("confirm"):
        return _error("edited", status=409)

    language = data.get("language") or concept.language
    try:
        produced = ai.generate_output(
            concept, _selections(concept), language, user=request.user,
        )
    except ai.AiError as exc:
        return _ai_failed(exc)

    if release is None:
        membership = getattr(request.user, "exo_membership", None)
        default_visibility = (
            PressRelease.Visibility.PRIVATE
            if membership and membership.default_visibility == "private"
            else PressRelease.Visibility.PUBLIC
        )
        release = PressRelease(concept=concept, visibility=default_visibility)
    release.headline = produced["headline"]
    release.body = produced["body"]
    release.document_body = produced["document_body"]
    release.language = language
    release.edited_by_owner = False
    if release.newspaper_style is None:
        release.newspaper_style = NewspaperStyle.objects.filter(
            is_active=True
        ).first()
    release.save()

    try:
        scored = ai.score(concept, release, language, user=request.user)
    except ai.AiError:
        scored = None  # a missing score is not a failed release
    if scored:
        release.exponential_score = scored["score"]
        release.score_rationale = scored["rationale"]
        release.save(update_fields=["exponential_score", "score_rationale"])

    held = _screen_before_the_wall(release, request.user)
    return JsonResponse({"ok": True, "held_back": held or "",
                         "visibility": release.visibility})


@member_required
@require_POST
def output_edit(request, pk):
    """Edit the text by hand — a real object, fixable without admin."""
    concept = get_owned_or_404(request, pk)
    release = getattr(concept, "release", None)
    if release is None:
        return _error("not found", status=404)
    try:
        data = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return _error("bad request")
    for field in ("headline", "body", "document_body"):
        if field in data:
            setattr(release, field, str(data[field]).strip())
    release.edited_by_owner = True
    release.save()
    # An edit is a new text on a public wall, so it is screened like any other
    # (G6). Otherwise "generate something bland, then edit it" is an open door.
    held = _screen_before_the_wall(release, request.user)
    return JsonResponse({"ok": True, "held_back": held or "",
                         "visibility": release.visibility})


@member_required
@require_POST
def output_style(request, pk):
    """Switch the paper. Re-renders the same content — never regenerates."""
    concept = get_owned_or_404(request, pk)
    release = getattr(concept, "release", None)
    if release is None:
        return _error("not found", status=404)
    try:
        data = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return _error("bad request")
    style = NewspaperStyle.objects.filter(
        key=data.get("style"), is_active=True,
    ).first()
    if style is None:
        return _error("not found", status=404)
    release.newspaper_style = style
    release.save(update_fields=["newspaper_style", "updated_at"])
    return JsonResponse({"ok": True, "css_class": style.css_class})


@member_required
@require_POST
def output_stress_test(request, pk):
    concept = get_owned_or_404(request, pk)
    release = getattr(concept, "release", None)
    if release is None:
        return _error("not found", status=404)
    try:
        points = ai.stress_test(
            concept, release, release.language, user=request.user,
        )
    except ai.AiError as exc:
        return _ai_failed(exc)
    release.stress_test_feedback = "\n".join(points)
    release.save(update_fields=["stress_test_feedback", "updated_at"])
    return JsonResponse({"points": points})


@member_required
@require_POST
def output_visibility(request, pk):
    """Who can see it, and for how long (spec §7.1)."""
    concept = get_owned_or_404(request, pk)
    release = getattr(concept, "release", None)
    if release is None:
        return _error("not found", status=404)
    try:
        data = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return _error("bad request")

    visibility = data.get("visibility")
    if visibility not in dict(PressRelease.Visibility.choices):
        return _error("bad visibility")
    release.visibility = visibility

    if visibility == PressRelease.Visibility.TIMED:
        hours = data.get("hours")
        try:
            hours = max(1, min(24 * 30, int(hours)))
        except (TypeError, ValueError):
            return _error("bad hours")
        release.public_until = timezone.now() + timezone.timedelta(hours=hours)
    else:
        release.public_until = None
    release.save(update_fields=["visibility", "public_until", "updated_at"])

    held = _screen_before_the_wall(release, request.user)
    if held:
        return JsonResponse({
            "ok": False, "held_back": held,
            "visibility": release.visibility,
        }, status=409)

    if visibility == PressRelease.Visibility.SPECIFIC:
        from django.contrib.auth import get_user_model

        emails = [e.strip() for e in (data.get("emails") or []) if e.strip()]
        people = get_user_model().objects.filter(email__in=emails)
        release.shared_with.set(people)

    return JsonResponse({
        "ok": True,
        "visibility": release.visibility,
        "public_until": release.public_until.isoformat() if release.public_until else None,
        "shared": release.shared_with.count(),
    })
