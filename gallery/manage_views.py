"""Avi's screens (REQ-G.90 to G.94): the numbers, trainings, topics and people.

Admin only; anybody else gets a 404, so the screens do not announce that they
exist. Every count is a subquery of its own, never a Count beside another join,
so one relation cannot inflate another (methodology 20).
"""

from decimal import Decimal
from functools import wraps

from django.db.models import Count, DecimalField, IntegerField, OuterRef, Q, Subquery, Sum, Value
from django.db.models.functions import Coalesce
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.text import slugify

from . import access
from .models import AICall, Exhibit, Person, Skill, SkillChat, Strike, Topic, Training
from .strings import text


def admin_only(view):
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if not access.is_admin(request.user):
            raise Http404
        request.gallery_person = access.ensure_person(request.user)
        return view(request, *args, **kwargs)

    return wrapped


def _count(model, field, **filters):
    return Coalesce(Subquery(
        model.objects.filter(**{field: OuterRef("pk")}, **filters).order_by().values(field)
        .annotate(n=Count("pk")).values("n")[:1], output_field=IntegerField()), Value(0))


def _cost(field):
    return Coalesce(Subquery(
        AICall.objects.filter(**{field: OuterRef("pk")}).order_by().values(field)
        .annotate(s=Sum("cost_usd")).values("s")[:1], output_field=DecimalField(max_digits=10, decimal_places=4)),
        Value(Decimal("0")), output_field=DecimalField(max_digits=10, decimal_places=4))


def people_rows():
    return (Person.objects.select_related("user", "training")
            .annotate(n_pages=_count(Exhibit, "owner", kind=Exhibit.PAGE),
                      n_skills=_count(Exhibit, "owner", kind=Exhibit.SKILL),
                      n_strikes=_count(Strike, "person", cleared_at__isnull=True),
                      cost=_cost("person"))
            .order_by("-created_at"))


def numbers():
    """REQ-G.94: real numbers from the rows, nothing estimated."""
    rows = list(people_rows())
    by_training = {}
    for p in rows:
        if p.training_id:
            key = p.training_id
        elif p.answered_training:
            key = "other"
        else:
            key = "none"
        b = by_training.setdefault(key, {"people": 0, "pages": 0, "skills": 0, "cost": Decimal("0")})
        b["people"] += 1
        b["pages"] += p.n_pages
        b["skills"] += p.n_skills
        b["cost"] += p.cost
    trainings = []
    for t in Training.objects.all():
        trainings.append((t, by_training.get(t.pk, {"people": 0, "pages": 0, "skills": 0, "cost": Decimal("0")})))
    total_cost = AICall.objects.aggregate(s=Sum("cost_usd"))["s"] or Decimal("0")
    return {
        "trainings": trainings,
        "other": by_training.get("other"), "unanswered": by_training.get("none"),
        "top_cost": sorted([p for p in rows if p.cost > 0], key=lambda p: -p.cost)[:15],
        "ceiling_chats": SkillChat.objects.filter(status=SkillChat.OUT_OF_BUDGET).select_related("person")[:30],
        "total_cost": total_cost,
        "calls": AICall.objects.count(),
        "totals": {"people": len(rows), "pages": Exhibit.objects.filter(kind=Exhibit.PAGE).count(),
                   "skills": Skill.objects.count(), "bkms": Exhibit.objects.filter(kind=Exhibit.BKM).count()},
        "others_said": [p for p in rows if p.training_other][:30],
    }


@admin_only
def home(request):
    return render(request, "gallery/manage_numbers.html", {"section": "manage", "tab": "numbers", **numbers()})


def _move(model, pk, step):
    rows = list(model.objects.all())
    i = next((n for n, r in enumerate(rows) if r.pk == pk), None)
    j = None if i is None else i + step
    if i is None or j < 0 or j >= len(rows):
        return
    rows[i], rows[j] = rows[j], rows[i]
    for n, r in enumerate(rows):
        if r.position != (n + 1) * 10:
            r.position = (n + 1) * 10
            r.save(update_fields=["position"])


def _next_position(model):
    last = model.objects.order_by("-position").values_list("position", flat=True).first() or 0
    return last + 10


@admin_only
def trainings(request):
    """REQ-G.91"""
    error = ""
    if request.method == "POST":
        action = request.POST.get("action")
        he, en = (request.POST.get("name_he") or "").strip()[:120], (request.POST.get("name_en") or "").strip()[:120]
        if action == "add":
            if he or en:
                Training.objects.create(name_he=he or en, name_en=en or he, position=_next_position(Training))
                return redirect("gallery:manage_trainings")
            error = text("manage.need_name", request.gallery_language)
        else:
            t = get_object_or_404(Training, pk=request.POST.get("pk"))
            if action == "save" and (he or en):
                t.name_he, t.name_en = he or en, en or he
                t.save(update_fields=["name_he", "name_en"])
            elif action == "toggle":
                t.is_open = not t.is_open
                t.save(update_fields=["is_open"])
            elif action in ("up", "down"):
                _move(Training, t.pk, -1 if action == "up" else 1)
            return redirect("gallery:manage_trainings")
    rows = Training.objects.annotate(n_people=Count("people"))
    return render(request, "gallery/manage_trainings.html",
                  {"section": "manage", "tab": "trainings", "rows": rows, "error": error})


@admin_only
def topics(request):
    """REQ-G.92"""
    error = ""
    if request.method == "POST":
        action = request.POST.get("action")
        he, en = (request.POST.get("name_he") or "").strip()[:60], (request.POST.get("name_en") or "").strip()[:60]
        if action == "add":
            slug = slugify(en or he)[:60]
            if not (he or en) or not slug:
                error = text("manage.need_english", request.gallery_language)
            elif Topic.objects.filter(slug=slug).exists():
                error = text("manage.topic_exists", request.gallery_language)
            else:
                Topic.objects.create(name_he=he or en, name_en=en or he, slug=slug, position=_next_position(Topic))
                return redirect("gallery:manage_topics")
        else:
            t = get_object_or_404(Topic, pk=request.POST.get("pk"))
            if action == "save" and (he or en):
                t.name_he, t.name_en = he or en, en or he
                t.save(update_fields=["name_he", "name_en"])
            elif action in ("up", "down"):
                _move(Topic, t.pk, -1 if action == "up" else 1)
            return redirect("gallery:manage_topics")
    rows = Topic.objects.annotate(n_cards=Count("exhibits"))
    return render(request, "gallery/manage_topics.html",
                  {"section": "manage", "tab": "topics", "rows": rows, "error": error})


@admin_only
def people(request):
    """REQ-G.93: who, from where, what they posted, strikes, cost; and the
    three levers: unlimited skills, unblock, reset a skill's updates."""
    if request.method == "POST":
        action = request.POST.get("action")
        if action == "reset_updates":
            skill = get_object_or_404(Skill, pk=request.POST.get("skill"))
            skill.updates_used = 0
            skill.save(update_fields=["updates_used"])
        else:
            p = get_object_or_404(Person, pk=request.POST.get("pk"))
            if action == "unlimited":
                p.unlimited_skills = not p.unlimited_skills
                p.save(update_fields=["unlimited_skills"])
            elif action == "unblock":
                p.skills_blocked_at = None
                p.save(update_fields=["skills_blocked_at"])
                # A lifted block starts clean: the old strikes stay on record but no longer count.
                p.strikes.filter(cleared_at__isnull=True).update(cleared_at=timezone.now())
        back = request.POST.get("back") or ""
        return redirect(back if back.startswith("/gallery/manage/") and "//" not in back else "gallery:manage_people")
    q = (request.GET.get("q") or "").strip()[:100]
    rows = people_rows()
    if q:
        rows = rows.filter(Q(display_name__icontains=q) | Q(user__email__icontains=q))
    if request.GET.get("show") == "blocked":
        rows = rows.filter(skills_blocked_at__isnull=False)
    return render(request, "gallery/manage_people.html", {
        "section": "manage", "tab": "people", "rows": rows[:300], "q": q, "show": request.GET.get("show", ""),
    })


@admin_only
def person(request, pk):
    p = get_object_or_404(people_rows(), pk=pk)
    return render(request, "gallery/manage_person.html", {
        "section": "manage", "tab": "people", "p": p,
        "skills": Skill.objects.filter(exhibit__owner=p).select_related("exhibit"),
        "strikes": p.strikes.select_related("chat"),
        "chats": p.skill_chats.all()[:30],
        "calls": p.ai_calls.all()[:50],
        "now": timezone.now(),
    })
