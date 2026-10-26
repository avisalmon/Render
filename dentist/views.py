"""dentist's screens (spec chapter 11). Every clinical view goes through
`access.require_member` or `require_admin`, every look at a patient writes
a log row, and every screen is tagged for its persona in its template.

D.1: the front door, sign-in, the clinic's home. D.2: people and setup.
D.3: the patient record, the log, export and deletion, the patient's own
door and screen.
"""

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify
from django.views.decorators.http import require_POST

from . import access, mouth, people, records
from .decorators import signed_in
from .forms import ClinicForm, HistoryForm, PatientForm
from .models import (
    SURFACES,
    Chair,
    Clinic,
    ClinicMember,
    Invitation,
    PatientLink,
    PlanItem,
    ToothState,
    VisitProcedure,
)


def _clinic(slug):
    return get_object_or_404(Clinic, slug=slug)


def _ctx(clinic, member, **more):
    return {"clinic": clinic, "member": member, "is_admin": member.role == ClinicMember.ADMIN, **more}


# ------------------------------------------------------------ the front door


def home(request):
    """**Front door, every persona.** Signed out: what this is, and the way
    in. Signed in: the clinics this person belongs to, or their own record,
    or (a superuser with nothing) the one thing they may do."""
    if not request.user.is_authenticated:
        return render(request, "dentist/home.html", {"signed_out": True})

    mine = list(access.memberships(request.user))
    me = access.patient_of(request.user)
    tried = access.trying(request.user)
    if me is not None and tried and tried["role"] == "patient":
        return redirect("dentist:me")  # trying the clinic as a patient (Rule 3.7)
    if len(mine) == 1 and me is None:
        return redirect("dentist:clinic_home", slug=mine[0].clinic.slug)
    if me is not None and not mine and not access.may_create_clinic(request.user):
        return redirect("dentist:me")
    return render(request, "dentist/home.html", {
        "memberships": mine,
        "patient": me,
        "may_create": access.may_create_clinic(request.user),
    })


@signed_in
def clinic_new(request):
    """**Site admin.** Rule 3.3: the superuser's one power. Creates the
    clinic and invites its first administrator by email; the superuser is
    not made a member and sees nothing more."""
    if not access.may_create_clinic(request.user):
        raise PermissionDenied

    errors = {}
    data = {"name": "", "admin_email": ""}
    if request.method == "POST":
        data = {k: (request.POST.get(k) or "").strip() for k in data}
        if not data["name"]:
            errors["name"] = "Give the clinic a name."
        if "@" not in data["admin_email"]:
            errors["admin_email"] = "The first administrator's email address."
        slug = slugify(data["name"])[:70]
        if not errors and (not slug or Clinic.objects.filter(slug=slug).exists()):
            errors["name"] = "A clinic with this name already exists."
        if not errors:
            with transaction.atomic():
                clinic = Clinic.objects.create(
                    name=data["name"], slug=slug, created_by=request.user,
                    languages=["he", "en", "ru", "ar", "ti", "hi"],
                )
            _, sent = people.invite(clinic, data["admin_email"], ClinicMember.ADMIN, request.user, request)
            if sent:
                messages.success(request, f"{clinic.name} exists. Its first administrator has an invitation "
                                          f"at {data['admin_email']}; you are not a member of it.")
            else:
                messages.warning(request, f"{clinic.name} exists, but the invitation mail to "
                                          f"{data['admin_email']} was not sent. Try again from the clinic's "
                                          "people screen once an administrator is in, or check the mail setup.")
            return redirect("dentist:home")
    return render(request, "dentist/clinic_new.html", {"errors": errors, "data": data})


@signed_in
def clinic_home(request, slug):
    """**Administrator or dentist.** The clinic's home, answering "what now"
    for this person's role (Rule 11.5)."""
    clinic = _clinic(slug)
    member = access.require_member(request.user, clinic)
    access.log(clinic, request.user, "viewed", what="clinic home")
    return render(request, "dentist/clinic_home.html", _ctx(clinic, member, counts={
        "patients": clinic.patients.filter(status="active").count(),
        "members": clinic.members.filter(active=True).count(),
        "chairs": clinic.chairs.filter(active=True).count(),
        "pending": clinic.invitations.filter(accepted_at__isnull=True).count(),
    }))


# --------------------------------------------------------- D.2: people, setup


@signed_in
def people_screen(request, slug):
    """**Administrator.** Who is in the clinic, who is invited, invite
    another (Rule 3.2)."""
    clinic = _clinic(slug)
    member = access.require_admin(request.user, clinic)
    errors = {}
    data = {"email": "", "role": ClinicMember.DENTIST}
    if request.method == "POST":
        data = {k: (request.POST.get(k) or "").strip() for k in data}
        if "@" not in data["email"]:
            errors["email"] = "An email address."
        if data["role"] not in dict(ClinicMember.ROLES):
            errors["role"] = "Dentist or administrator."
        if not errors and clinic.members.filter(user__email__iexact=data["email"], active=True).exists():
            errors["email"] = "Already a member of this clinic."
        if not errors:
            invitation, sent = people.invite(clinic, data["email"], data["role"], request.user, request)
            if sent:
                messages.success(request, f"Invitation sent to {invitation.email}.")
            else:
                messages.warning(request, f"The invitation for {invitation.email} exists but the mail was "
                                          "not sent. Resend it, or give them the link by hand.")
            return redirect("dentist:people", slug=slug)
    return render(request, "dentist/people.html", _ctx(
        clinic, member, errors=errors, data=data, roles=ClinicMember.ROLES,
        members=clinic.members.select_related("user").order_by("-active", "role", "id"),
        invitations=clinic.invitations.filter(accepted_at__isnull=True),
    ))


@signed_in
@require_POST
def member_toggle(request, slug, pk):
    """Deactivate, or bring back. Never deletes: the visits they signed
    still name them."""
    clinic = _clinic(slug)
    me = access.require_admin(request.user, clinic)
    target = get_object_or_404(clinic.members, pk=pk)
    if target.pk == me.pk:
        messages.error(request, "You cannot deactivate yourself. Ask another administrator.")
        return redirect("dentist:people", slug=slug)
    target.active = not target.active
    target.save(update_fields=["active"])
    access.log(clinic, request.user, "edited", what=f"member {target.pk} {'active' if target.active else 'inactive'}")
    return redirect("dentist:people", slug=slug)


@signed_in
@require_POST
def invitation_action(request, slug, pk, what):
    clinic = _clinic(slug)
    access.require_admin(request.user, clinic)
    invitation = get_object_or_404(clinic.invitations.filter(accepted_at__isnull=True), pk=pk)
    if what == "cancel":
        invitation.delete()
        messages.success(request, "Invitation withdrawn.")
    else:
        if people.resend(invitation, request):
            messages.success(request, f"Sent again to {invitation.email}.")
        else:
            messages.warning(request, f"Not sent to {invitation.email}. Give them the link by hand.")
    return redirect("dentist:people", slug=slug)


def accept_invitation(request, token):
    """Landing on the link from the invitation mail. Signed out: the way in,
    with the role waiting. Signed in: the role, once, then the clinic."""
    invitation = get_object_or_404(Invitation, token=token)
    if not request.user.is_authenticated:
        return render(request, "dentist/accept.html", {
            "invitation": invitation, "next": request.path,
            "google_url": "/accounts/google/login/?process=login&next=" + request.path,
        })
    try:
        member, made = people.accept(invitation, request.user)
    except people.Refused as exc:
        messages.error(request, str(exc))
        return redirect("dentist:home")
    if made:
        messages.success(request, f"You are {member.get_role_display().lower()} at {invitation.clinic.name}.")
    return redirect("dentist:clinic_home", slug=invitation.clinic.slug)


@signed_in
def setup(request, slug):
    """**Administrator.** The clinic's own setup: name, address, hours,
    chairs (Rule 3.6)."""
    clinic = _clinic(slug)
    member = access.require_admin(request.user, clinic)
    form = ClinicForm(instance=clinic)
    if request.method == "POST" and request.POST.get("form") == "clinic":
        form = ClinicForm(request.POST, instance=clinic)
        if form.is_valid():
            form.save()
            access.log(clinic, request.user, "edited", what="clinic setup")
            messages.success(request, "Saved.")
            return redirect("dentist:setup", slug=slug)
    if request.method == "POST" and request.POST.get("form") == "chair":
        name = (request.POST.get("name") or "").strip()
        if name:
            Chair.objects.create(clinic=clinic, name=name, order=clinic.chairs.count())
            access.log(clinic, request.user, "edited", what="chair added")
        return redirect("dentist:setup", slug=slug)
    return render(request, "dentist/setup.html", _ctx(clinic, member, form=form, chairs=clinic.chairs.all()))


@signed_in
@require_POST
def chair_toggle(request, slug, pk):
    clinic = _clinic(slug)
    access.require_admin(request.user, clinic)
    chair = get_object_or_404(clinic.chairs, pk=pk)
    chair.active = not chair.active
    chair.save(update_fields=["active"])
    return redirect("dentist:setup", slug=slug)


# ------------------------------------------------------ D.3: the patient record


@signed_in
def patients(request, slug):
    """**Dentist and administrator.** One search box: name, number, phone;
    empty, the last few seen (Rule 4.6)."""
    clinic = _clinic(slug)
    member = access.require_member(request.user, clinic)
    q = request.GET.get("q", "")
    found = records.find(access.patients_for(request.user, clinic), q)
    return render(request, "dentist/patients.html", _ctx(clinic, member, q=q, patients=found,
                                                          total=clinic.patients.count()))


@signed_in
def patient_new(request, slug):
    """A record in ten seconds: a first name (Rule 4.1). Everything else
    later, on the record."""
    clinic = _clinic(slug)
    member = access.require_member(request.user, clinic)
    error = ""
    if request.method == "POST":
        first = (request.POST.get("first_name") or "").strip()
        if not first:
            error = "A first name is enough to start."
        else:
            patient = clinic.patients.create(first_name=first[:80], created_by=request.user,
                                             preferred_language=request.POST.get("preferred_language") or "en")
            access.log(clinic, request.user, "edited", patient=patient, what="patient created")
            messages.success(request, f"{patient.first_name} has the number {patient.clinic_number}.")
            return redirect("dentist:patient", slug=slug, pk=patient.pk)
    from .models import LANGUAGES
    return render(request, "dentist/patient_new.html", _ctx(clinic, member, error=error, languages=LANGUAGES))


@signed_in
def patient(request, slug, pk):
    """**Dentist and administrator.** One patient: alerts first, then who
    they are, history, plan, appointments (Rule 11.2). Every opening is a
    log row (Rule 4.5)."""
    clinic = _clinic(slug)
    member = access.require_member(request.user, clinic)
    person = access.patient_or_404(request.user, clinic, pk)
    access.log(clinic, request.user, "viewed", patient=person, what="patient record")
    link = person.links.filter(used_at__isnull=True).order_by("-made_at").first() if member.role == ClinicMember.ADMIN else None
    if link is not None and not link.is_valid:
        link = None
    history_form = HistoryForm()
    if request.method == "POST" and request.POST.get("form") == "history":
        history_form = HistoryForm(request.POST)
        if history_form.is_valid():
            item = history_form.save(commit=False)
            item.patient, item.noted_by = person, request.user
            item.save()
            access.log(clinic, request.user, "edited", patient=person, what="history added")
            return redirect("dentist:patient", slug=slug, pk=pk)
    return render(request, "dentist/patient.html", _ctx(
        clinic, member, patient=person,
        alerts=person.alerts, history=person.history.filter(active=True), resolved=person.history.filter(active=False),
        plan=person.plan.exclude(status="dropped"), appointments=person.appointments.order_by("-starts_at", "-arrived_at")[:8],
        link=link, link_url=(request.build_absolute_uri(f"/dentist/join/{link.token}/") if link else ""),
        history_form=history_form,
    ))


@signed_in
def patient_edit(request, slug, pk):
    clinic = _clinic(slug)
    member = access.require_member(request.user, clinic)
    person = access.patient_or_404(request.user, clinic, pk)
    form = PatientForm(request.POST or None, instance=person)
    if request.method == "POST" and form.is_valid():
        form.save()
        access.log(clinic, request.user, "edited", patient=person, what="patient details")
        messages.success(request, "Saved.")
        return redirect("dentist:patient", slug=slug, pk=pk)
    return render(request, "dentist/patient_edit.html", _ctx(clinic, member, patient=person, form=form))


@signed_in
@require_POST
def history_resolve(request, slug, pk, item):
    """A resolved item is kept, inactive, never deleted (Rule 4.4)."""
    clinic = _clinic(slug)
    access.require_member(request.user, clinic)
    person = access.patient_or_404(request.user, clinic, pk)
    row = get_object_or_404(person.history, pk=item)
    row.active = False
    row.save(update_fields=["active"])
    access.log(clinic, request.user, "edited", patient=person, what="history resolved")
    return redirect("dentist:patient", slug=slug, pk=pk)


@signed_in
@require_POST
def patient_link_new(request, slug, pk):
    """**Administrator.** The one-time link that gives this patient a login
    (Rule 3.4). Shown on the record while it is live."""
    clinic = _clinic(slug)
    access.require_admin(request.user, clinic)
    person = access.patient_or_404(request.user, clinic, pk)
    if person.user_id:
        messages.error(request, "This patient already has an account.")
    else:
        people.make_patient_link(person, request.user, request)
        messages.success(request, f"A link for {person.first_name} is ready below. It works once and for "
                                  f"{people.LINK_DAYS} days.")
    return redirect("dentist:patient", slug=slug, pk=pk)


@signed_in
def patient_export(request, slug, pk):
    """**Administrator.** Everything about one person, as a file (Rule 9.5)."""
    clinic = _clinic(slug)
    access.require_admin(request.user, clinic)
    person = access.patient_or_404(request.user, clinic, pk)
    body = records.export(person, request.user)
    response = HttpResponse(body, content_type="application/json; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{clinic.slug}-{person.clinic_number}.json"'
    return response


@signed_in
def patient_delete(request, slug, pk):
    """**Administrator.** Asks twice: the page states the consequence and
    wants the clinic number typed (Rule 9.5, 11.6)."""
    clinic = _clinic(slug)
    member = access.require_admin(request.user, clinic)
    person = access.patient_or_404(request.user, clinic, pk)
    error = ""
    if request.method == "POST":
        if (request.POST.get("confirm") or "").strip().upper() != person.clinic_number.upper():
            error = "Type the clinic number exactly as shown."
        else:
            number = person.clinic_number
            records.delete(person, request.user)
            messages.success(request, f"{number} and everything about them has been deleted.")
            return redirect("dentist:patients", slug=slug)
    return render(request, "dentist/patient_delete.html", _ctx(clinic, member, patient=person, error=error, counts={
        "history": person.history.count(), "teeth": person.teeth.count(), "visits": person.visits.count(),
        "files": person.attachments.count(), "appointments": person.appointments.count(),
    }))


@signed_in
def access_log(request, slug):
    """**Administrator.** Who looked (Rule 4.5). Ids and screens, never
    names of what was read (Rule 9.4); the patient's number is looked up
    for the screen only."""
    clinic = _clinic(slug)
    member = access.require_admin(request.user, clinic)
    rows = clinic.access_log.select_related("user", "patient")[:200]
    return render(request, "dentist/access_log.html", _ctx(clinic, member, rows=rows))


# ------------------------------------------------------- D.3: the patient's door


def join(request, token):
    """The patient's link (Rule 3.4). Signed out: the way in, this record
    waiting. Signed in: the account becomes the record's, once."""
    link = get_object_or_404(PatientLink.objects.select_related("patient__clinic"), token=token)
    if not request.user.is_authenticated:
        return render(request, "dentist/join.html", {
            "link": link, "clinic": link.patient.clinic, "next": request.path,
            "google_url": "/accounts/google/login/?process=login&next=" + request.path,
        })
    try:
        people.connect(link, request.user)
    except people.Refused as exc:
        return render(request, "dentist/join.html", {"link": link, "clinic": link.patient.clinic,
                                                     "refused": str(exc)}, status=403)
    messages.success(request, "This is your record. Only you and the clinic can see it.")
    return redirect("dentist:me")


@signed_in
def me(request):
    """**Patient.** My next appointment first, large; then my appointments,
    my plan and what was done, my details (Rule 3.5, 7.6, 11.4). Never the
    dentist's notes. English in D.3; the six languages arrive in D.7."""
    person = access.patient_of(request.user)
    if person is None:
        return redirect("dentist:home")
    clinic = person.clinic
    access.log(clinic, request.user, "viewed", patient=person, what="own record")
    now = timezone.now()
    upcoming = person.appointments.filter(starts_at__gte=now, status__in=["booked", "arrived"]).order_by("starts_at")
    past = person.appointments.exclude(pk__in=upcoming.values("pk")).order_by("-starts_at", "-arrived_at")[:10]
    done = VisitProcedure.objects.filter(visit__patient=person).select_related("procedure", "visit").order_by("-visit__started_at")
    return render(request, "dentist/me.html", {
        "clinic": clinic, "patient": person, "next_one": upcoming.first(), "upcoming": upcoming[1:6], "past": past,
        "plan": person.plan.exclude(status="dropped"), "done": done,
    })


# ---------------------------------------------------- trying a role (demo)


@signed_in
@require_POST
def try_as(request, slug):
    """**Administrator of a demo clinic** (Rule 3.7). Choose to see the
    clinic as a dentist, as one of its demo patients, or as yourself
    again. Session state only; checked by access.py on every request."""
    clinic = _clinic(slug)
    if not access.may_try(request.user, clinic):
        raise PermissionDenied
    role = request.POST.get("role")
    if role not in access.TRY_ROLES:
        raise Http404
    if role == "admin":
        request.session.pop(access.TRY_KEY, None)
        return redirect("dentist:clinic_home", slug=slug)
    state = {"clinic": slug, "role": role}
    if role == "patient":
        patient = clinic.patients.filter(is_demo=True, pk=request.POST.get("patient") or 0).first() \
            or clinic.patients.filter(is_demo=True).order_by("first_name").first()
        if patient is None:
            messages.error(request, "This clinic has no demo patient to try.")
            return redirect("dentist:clinic_home", slug=slug)
        state["patient"] = patient.pk
    request.session[access.TRY_KEY] = state
    access.log(clinic, request.user, "viewed", what=f"trying the clinic as {role}")
    return redirect("dentist:me" if role == "patient" else "dentist:clinic_home", **({} if role == "patient" else {"slug": slug}))


# ------------------------------------------------------------- D.4: the mouth


def _mouth_context(request, clinic, member, person, child):
    latest = mouth.chart(person)
    selected = mouth.valid_tooth(request.GET.get("tooth") or request.POST.get("tooth"))
    return _ctx(
        clinic, member, patient=person, child=child, rows=mouth.layout(person, child=child, latest=latest),
        selected=selected, history=mouth.history_of(person, selected) if selected else [],
        surfaces=[("", "Whole"), ("M", "M"), ("D", "D"), ("B", "B"), ("L", "L"), ("O", "O")],
        conditions=ToothState.CONDITIONS, last_condition=request.session.get("dn_last_condition", "decay"),
        plan=person.plan.exclude(status="dropped"), dropped=person.plan.filter(status="dropped"),
        procedures=clinic.procedures.filter(active=True), alerts=person.alerts,
    )


def _wants_child(request, person):
    flag = request.GET.get("child")
    return flag == "1" if flag is not None else mouth.has_child_teeth(person)


@signed_in
def mouth_screen(request, slug, pk):
    """**Dentist.** The chart as a mouth and the plan under it (Rule 5.1 to
    5.3, 11.2): one tap on a tooth opens its state, two record the common
    case. Every opening is a log row."""
    clinic = _clinic(slug)
    member = access.require_member(request.user, clinic)
    person = access.patient_or_404(request.user, clinic, pk)
    access.log(clinic, request.user, "viewed", patient=person, what="mouth")
    return render(request, "dentist/mouth.html", _mouth_context(request, clinic, member, person, _wants_child(request, person)))


@signed_in
@require_POST
def tooth_record(request, slug, pk):
    """A new dated, authored row; never an edit of an old one (Rule 5.1)."""
    clinic = _clinic(slug)
    access.require_member(request.user, clinic)
    person = access.patient_or_404(request.user, clinic, pk)
    tooth = mouth.valid_tooth(request.POST.get("tooth"))
    surface = request.POST.get("surface") or ""
    condition = request.POST.get("condition") or ""
    back = reverse("dentist:mouth", args=[slug, pk]) + f"?tooth={tooth or ''}" + ("&child=1" if request.POST.get("child") == "1" else "")
    if tooth is None or surface not in dict(SURFACES) or condition not in dict(ToothState.CONDITIONS):
        messages.error(request, "Pick a tooth, a surface and a condition.")
        return redirect(back)
    ToothState.objects.create(patient=person, tooth=tooth, surface=surface, condition=condition,
                              note=(request.POST.get("note") or "")[:240], noted_by=request.user)
    request.session["dn_last_condition"] = condition
    access.log(clinic, request.user, "edited", patient=person, what=f"tooth {tooth}{surface} recorded")
    return redirect(back)


@signed_in
@require_POST
def plan_add(request, slug, pk):
    clinic = _clinic(slug)
    access.require_member(request.user, clinic)
    person = access.patient_or_404(request.user, clinic, pk)
    procedure = clinic.procedures.filter(active=True, pk=request.POST.get("procedure") or 0).first()
    if procedure is None:
        messages.error(request, "Pick a procedure from the clinic's list.")
    else:
        last = person.plan.exclude(status="dropped").order_by("-priority").values_list("priority", flat=True).first() or 0
        PlanItem.objects.create(patient=person, procedure=procedure, tooth=mouth.valid_tooth(request.POST.get("tooth")),
                                priority=last + 1, note=(request.POST.get("note") or "")[:240], planned_by=request.user)
        access.log(clinic, request.user, "edited", patient=person, what="plan item added")
    return redirect("dentist:mouth", slug=slug, pk=pk)


@signed_in
@require_POST
def plan_item_action(request, slug, pk, item, what):
    """Move up or down, or drop. Done is never set here: doing the
    procedure in a visit marks it (Rule 5.3, sprint D.6)."""
    clinic = _clinic(slug)
    access.require_member(request.user, clinic)
    person = access.patient_or_404(request.user, clinic, pk)
    row = get_object_or_404(person.plan, pk=item)
    live = list(person.plan.exclude(status="dropped").order_by("priority", "id"))
    if what == "drop":
        row.status = "dropped"
        row.save(update_fields=["status"])
    elif what in ("up", "down") and row in live:
        i = live.index(row)
        j = i - 1 if what == "up" else i + 1
        if 0 <= j < len(live):
            live[i], live[j] = live[j], live[i]
            for n, r in enumerate(live, start=1):
                if r.priority != n:
                    r.priority = n
                    r.save(update_fields=["priority"])
    else:
        raise Http404
    access.log(clinic, request.user, "edited", patient=person, what=f"plan item {what}")
    return redirect("dentist:mouth", slug=slug, pk=pk)


@signed_in
def patient_print(request, slug, pk):
    """The chart and the plan on one page, for a patient who takes it to
    another clinic (Rule 5.4). Logged as printed."""
    clinic = _clinic(slug)
    member = access.require_member(request.user, clinic)
    person = access.patient_or_404(request.user, clinic, pk)
    access.log(clinic, request.user, "printed", patient=person, what="chart and plan")
    child = _wants_child(request, person)
    return render(request, "dentist/print.html", _ctx(
        clinic, member, patient=person, child=child, rows=mouth.layout(person, child=child),
        plan=person.plan.exclude(status="dropped"), alerts=person.alerts, now=timezone.now(),
        notes=person.teeth.exclude(note="").order_by("-noted_at", "-id")[:20],
    ))
