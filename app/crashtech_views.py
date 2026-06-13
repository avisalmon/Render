"""CrashTech views — SPR-6.5.1 Foundations: organizer setup, challenge
authoring, judge assignment. Public/live surfaces arrive in later sprints."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from .crashtech import (
    available_stock,
    can_configure,
    can_create_hackathon,
    compute_leaderboard,
    final_ranking,
    grant_role,
    manager_required,
    organizer_required,
    review_required,
    roles_of,
    team_of,
)
from .models import (
    Certificate,
    Challenge,
    GloryPage,
    Hackathon,
    QRToken,
    Submission,
    Team,
)


def _aware(value):
    """Parse a datetime-local string into an aware datetime (or None)."""
    if not value:
        return None
    dt = parse_datetime(value)
    if dt is None:
        return None
    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt, timezone.get_current_timezone())
    return dt


def _parse_tiers(raw):
    """'50, 30, 10' -> [50, 30, 10]; tolerant of junk."""
    out = []
    for part in (raw or "").replace("\n", ",").split(","):
        part = part.strip()
        if part.isdigit():
            out.append(int(part))
    return out


def crashtech_home(request):
    """Public index of hackathons (read-public). Organizers also see their
    setup/readiness drafts."""
    public = Hackathon.objects.exclude(status="setup")
    mine = []
    if request.user.is_authenticated:
        mine = Hackathon.objects.filter(organizer=request.user)
    return render(request, "app/crashtech/home.html", {
        "hackathons": public, "mine": mine,
        "can_create": can_create_hackathon(request.user),
    })


@login_required
def hackathon_create(request):
    """REQ-6.5.3: staff create a hackathon and become its organizer."""
    if not can_create_hackathon(request.user):
        from django.http import HttpResponseForbidden
        return HttpResponseForbidden("רק צוות babook יכול ליצור האקתון")
    if request.method == "POST":
        start = _aware(request.POST.get("start_at"))
        end = _aware(request.POST.get("end_at"))
        deadline = _aware(request.POST.get("submission_deadline")) or end
        name = (request.POST.get("name") or "").strip()
        if not (name and start and end):
            messages.error(request, "שם, מועד התחלה וסיום הם שדות חובה.")
            return render(request, "app/crashtech/hackathon_form.html", {"h": None})
        h = Hackathon.objects.create(
            name=name, start_at=start, end_at=end, submission_deadline=deadline,
            team_size=int(request.POST.get("team_size") or 3),
            hardware_stock=int(request.POST.get("hardware_stock") or 0),
            github_repo_url=(request.POST.get("github_repo_url") or "").strip()[:500],
            organizer=request.user,
        )
        grant_role(h, request.user, "organizer")
        messages.success(request, "ההאקתון נוצר! עכשיו אפשר להגדיר אתגרים ושופטים.")
        return redirect("crashtech_manage", slug=h.slug)
    return render(request, "app/crashtech/hackathon_form.html", {"h": None})


@organizer_required
def hackathon_edit(request, hackathon):
    """REQ-6.5.3: edit config (pre-kickoff)."""
    if request.method == "POST":
        if not hackathon.can_edit_setup:
            messages.error(request, "אי אפשר לשנות הגדרות אחרי תחילת האירוע.")
            return redirect("crashtech_manage", slug=hackathon.slug)
        hackathon.name = (request.POST.get("name") or hackathon.name).strip()
        hackathon.start_at = _aware(request.POST.get("start_at")) or hackathon.start_at
        hackathon.end_at = _aware(request.POST.get("end_at")) or hackathon.end_at
        hackathon.submission_deadline = (
            _aware(request.POST.get("submission_deadline")) or hackathon.submission_deadline
        )
        hackathon.team_size = int(request.POST.get("team_size") or hackathon.team_size)
        hackathon.hardware_stock = int(request.POST.get("hardware_stock") or hackathon.hardware_stock)
        hackathon.github_repo_url = (request.POST.get("github_repo_url") or "").strip()[:500]
        hackathon.save()
        messages.success(request, "ההגדרות נשמרו.")
        return redirect("crashtech_manage", slug=hackathon.slug)
    return render(request, "app/crashtech/hackathon_form.html", {"h": hackathon})


@organizer_required
def hackathon_manage(request, hackathon):
    """Organizer dashboard: config, challenges, judges, lifecycle advance."""
    if request.method == "POST" and request.POST.get("action") == "advance":
        if hackathon.advance():
            messages.success(request, f"האירוע עבר לשלב «{hackathon.status_label}».")
        return redirect("crashtech_manage", slug=hackathon.slug)
    judges = User.objects.filter(crashtech_roles__hackathon=hackathon,
                                 crashtech_roles__role="judge").distinct()
    return render(request, "app/crashtech/manage.html", {
        "h": hackathon,
        "challenges": hackathon.challenges.all(),
        "judges": judges,
        "statuses": Hackathon.STATUS_ORDER,
    })


@organizer_required
def challenge_create(request, hackathon):
    """REQ-6.5.4: author a (secret) challenge."""
    if request.method == "POST":
        title = (request.POST.get("title") or "").strip()
        if not title:
            messages.error(request, "כותרת האתגר חובה.")
            return redirect("crashtech_manage", slug=hackathon.slug)
        Challenge.objects.create(
            hackathon=hackathon, title=title,
            description=(request.POST.get("description") or "").strip(),
            point_value=int(request.POST.get("point_value") or 0),
            scoring_mode=request.POST.get("scoring_mode") or "pass_fail",
            top_submission_count=int(request.POST.get("top_submission_count") or 0),
            bonus_points_tiers=_parse_tiers(request.POST.get("bonus_points_tiers")),
            visible=False, created_by=request.user,
        )
        messages.success(request, "האתגר נוסף (חבוי עד הזינוק).")
        return redirect("crashtech_manage", slug=hackathon.slug)
    return render(request, "app/crashtech/challenge_form.html", {"h": hackathon, "ch": None})


@organizer_required
def challenge_edit(request, hackathon, challenge_id):
    ch = get_object_or_404(Challenge, pk=challenge_id, hackathon=hackathon)
    if request.method == "POST":
        ch.title = (request.POST.get("title") or ch.title).strip()
        ch.description = (request.POST.get("description") or "").strip()
        ch.point_value = int(request.POST.get("point_value") or 0)
        ch.scoring_mode = request.POST.get("scoring_mode") or ch.scoring_mode
        ch.top_submission_count = int(request.POST.get("top_submission_count") or 0)
        ch.bonus_points_tiers = _parse_tiers(request.POST.get("bonus_points_tiers"))
        ch.save()
        messages.success(request, "האתגר עודכן.")
        return redirect("crashtech_manage", slug=hackathon.slug)
    return render(request, "app/crashtech/challenge_form.html", {"h": hackathon, "ch": ch})


@organizer_required
def challenge_delete(request, hackathon, challenge_id):
    ch = get_object_or_404(Challenge, pk=challenge_id, hackathon=hackathon)
    if request.method == "POST":
        ch.delete()
        messages.success(request, "האתגר נמחק.")
    return redirect("crashtech_manage", slug=hackathon.slug)


@organizer_required
def judge_assign(request, hackathon):
    """REQ-6.5.5: organizer assigns/removes judges from babook users."""
    if request.method == "POST":
        username = (request.POST.get("username") or "").strip()
        action = request.POST.get("action", "add")
        target = User.objects.filter(username=username).first()
        if not target:
            messages.error(request, f"לא נמצא משתמש «{username}».")
        elif action == "remove":
            from .crashtech import revoke_role
            revoke_role(hackathon, target, "judge")
            messages.success(request, f"{target.username} הוסר מרשימת השופטים.")
        else:
            grant_role(hackathon, target, "judge")
            messages.success(request, f"{target.username} נוסף כשופט.")
        return redirect("crashtech_judges", slug=hackathon.slug)
    judges = User.objects.filter(crashtech_roles__hackathon=hackathon,
                                 crashtech_roles__role="judge").distinct()
    return render(request, "app/crashtech/judges.html", {"h": hackathon, "judges": judges})


@manager_required
def participants(request, hackathon):
    """REQ-6.5.6: organizer/admin invite existing babook users as participants."""
    if request.method == "POST":
        username = (request.POST.get("username") or "").strip()
        target = User.objects.filter(username=username).first()
        if not target:
            messages.error(request, f"לא נמצא משתמש «{username}».")
        else:
            grant_role(hackathon, target, "participant")
            _email_invite(request, hackathon, target)
            from .community import notify
            notify(target, verb="crashtech_invite",
                   text=f"הוזמנת להאקתון «{hackathon.name}»",
                   url=f"/crashtech/{hackathon.slug}/")
            messages.success(request, f"{target.username} הוזמן/ה כמשתתף/ת.")
        return redirect("crashtech_participants", slug=hackathon.slug)
    invited = User.objects.filter(crashtech_roles__hackathon=hackathon,
                                  crashtech_roles__role="participant").distinct()
    q = (request.GET.get("q") or "").strip()
    matches = []
    if q:
        matches = User.objects.filter(username__icontains=q).select_related("profile")[:10]
    return render(request, "app/crashtech/participants.html", {
        "h": hackathon, "invited": invited, "matches": matches, "q": q,
    })


def _email_invite(request, hackathon, user):
    if not user.email:
        return
    from django.conf import settings
    from django.core.mail import send_mail
    url = request.build_absolute_uri(f"/crashtech/{hackathon.slug}/")
    send_mail(
        f"הוזמנת להאקתון «{hackathon.name}»",
        f"שלום,\n\nהוזמנת להשתתף בהאקתון «{hackathon.name}» ב-babook.\n"
        f"פרטים והכנה: {url}\n\nבהצלחה!",
        getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@babook.co.il"),
        [user.email], fail_silently=True,
    )


@manager_required
def teams(request, hackathon):
    """REQ-6.5.7/8: form teams, bounded by hardware stock."""
    if request.method == "POST":
        name = (request.POST.get("name") or "").strip()
        if not name:
            messages.error(request, "שם הצוות חובה.")
        elif available_stock(hackathon) <= 0:
            messages.error(request, "אזל מלאי הערכות - אי אפשר ליצור צוותים נוספים.")
        elif Team.objects.filter(hackathon=hackathon, name=name).exists():
            messages.error(request, "כבר קיים צוות בשם הזה.")
        else:
            Team.objects.create(
                hackathon=hackathon, name=name,
                glory_consent=request.POST.get("glory_consent") == "on",
                anon_ordinal=hackathon.teams.count() + 1,
            )
            messages.success(request, f"הצוות «{name}» נוצר.")
        return redirect("crashtech_teams", slug=hackathon.slug)
    return render(request, "app/crashtech/teams.html", {
        "h": hackathon, "teams": hackathon.teams.prefetch_related("members__profile"),
        "available": available_stock(hackathon),
    })


@manager_required
def team_edit(request, hackathon, team_id):
    """Add/remove members (size-bound), hardware status, consent, rename."""
    team = get_object_or_404(Team, pk=team_id, hackathon=hackathon)
    if request.method == "POST":
        action = request.POST.get("action")
        if action == "add_member":
            target = User.objects.filter(username=(request.POST.get("username") or "").strip()).first()
            if not target:
                messages.error(request, "לא נמצא משתמש.")
            elif team.members.count() >= hackathon.team_size:
                messages.error(request, f"הצוות מלא (עד {hackathon.team_size} חברים).")
            else:
                team.members.add(target)
                grant_role(hackathon, target, "participant")
                messages.success(request, "חבר/ה נוסף/ה לצוות.")
        elif action == "remove_member":
            target = User.objects.filter(username=(request.POST.get("username") or "").strip()).first()
            if target:
                team.members.remove(target)
        elif action == "hardware":
            status = request.POST.get("hardware_status")
            if status in dict(Team.HARDWARE):
                team.hardware_status = status
                team.save(update_fields=["hardware_status"])
                messages.success(request, "סטטוס החומרה עודכן.")
        elif action == "rename":
            team.name = (request.POST.get("name") or team.name).strip()
            team.save(update_fields=["name"])
        elif action == "consent":
            team.glory_consent = request.POST.get("glory_consent") == "on"
            team.save(update_fields=["glory_consent"])
        return redirect("crashtech_teams", slug=hackathon.slug)
    return redirect("crashtech_teams", slug=hackathon.slug)


@manager_required
def hardware_inventory(request, hackathon):
    """REQ-6.5.8: stock / shipped / received overview."""
    teams_qs = hackathon.teams.all()
    counts = {s: teams_qs.filter(hardware_status=s).count() for s, _ in Team.HARDWARE}
    return render(request, "app/crashtech/hardware.html", {
        "h": hackathon, "teams": teams_qs, "counts": counts,
        "available": available_stock(hackathon),
    })


def hackathon_detail(request, slug):
    """The hackathon hub / Event Main Page (REQ-6.5.10). Public read once out of
    setup; for a team member during the live event it carries the submit forms
    + their submission statuses. Organizer can always preview."""
    h = get_object_or_404(Hackathon, slug=slug)
    if h.status == "setup" and not can_configure(request.user, h):
        from django.http import Http404
        raise Http404
    my_team = team_of(request.user, h)
    challenges = list(h.challenges.filter(visible=True)) if h.challenges_visible else []
    my_subs = {}
    if my_team:
        my_subs = {s.challenge_id: s for s in my_team.submissions.all()}
    return render(request, "app/crashtech/detail.html", {
        "h": h,
        "challenges": challenges,
        "my_roles": roles_of(request.user, h),
        "my_team": my_team,
        "my_subs": my_subs,
    })


def _submit_guard(request, hackathon, challenge_id):
    """Shared checks for a submission: live + before deadline + caller is on a
    team in this hackathon. Returns (team, challenge) or (None, error_message)."""
    challenge = get_object_or_404(Challenge, pk=challenge_id, hackathon=hackathon)
    if not hackathon.accepts_submissions:
        return None, "ההגשות סגורות (לפני הזינוק או אחרי הדדליין)."
    team = team_of(request.user, hackathon)
    if team is None:
        return None, "רק חברי צוות יכולים להגיש."
    return team, challenge


@login_required
def submit_solution(request, slug, challenge_id):
    """REQ-6.5.11/6.5.16: a team submits (video link + zip). Resubmission
    updates the same row and resets it to pending (REQ-6.5.14 groundwork)."""
    hackathon = get_object_or_404(Hackathon, slug=slug)
    if request.method != "POST":
        return redirect("crashtech_detail", slug=slug)
    team, challenge = _submit_guard(request, hackathon, challenge_id)
    if team is None:
        messages.error(request, challenge)  # error message
        return redirect("crashtech_detail", slug=slug)
    sub, _ = Submission.objects.get_or_create(challenge=challenge, team=team)
    video_url = (request.POST.get("video_url") or "").strip()
    if video_url:
        sub.video_url = video_url[:500]
    if request.FILES.get("source_code"):
        sub.source_code = request.FILES["source_code"]
    sub.status = "pending"          # (re)submission enters the pending queue
    sub.feedback_note = ""
    sub.save()
    messages.success(request, f"ההגשה ל«{challenge.title}» נקלטה וממתינה לשיפוט.")
    return redirect("crashtech_detail", slug=slug)


@login_required
def challenge_qr(request, slug, challenge_id):
    """REQ-6.5.11: show a QR that opens a phone upload form bound to this
    team+challenge (token = auth, so the phone needn't be logged in)."""
    hackathon = get_object_or_404(Hackathon, slug=slug)
    challenge = get_object_or_404(Challenge, pk=challenge_id, hackathon=hackathon)
    team = team_of(request.user, hackathon)
    if team is None:
        from django.http import HttpResponseForbidden
        return HttpResponseForbidden("רק חברי צוות יכולים להעלות וידאו")
    tok = QRToken.get_or_refresh(team, challenge)
    upload_url = request.build_absolute_uri(f"/crashtech/u/{tok.token}/")
    qr_img = f"https://api.qrserver.com/v1/create-qr-code/?size=240x240&data={upload_url}"
    return render(request, "app/crashtech/qr.html", {
        "h": hackathon, "challenge": challenge, "team": team,
        "upload_url": upload_url, "qr_img": qr_img,
    })


@review_required
def judge_queue(request, hackathon):
    """REQ-6.5.12: blind queue of submissions to review. Team identity is hidden
    from judges (DEC-57) — only the anonymous label is shown."""
    challenge_id = request.GET.get("challenge")
    subs = (Submission.objects.filter(challenge__hackathon=hackathon)
            .select_related("challenge", "team").order_by("status", "submitted_at"))
    if challenge_id:
        subs = subs.filter(challenge_id=challenge_id)
    return render(request, "app/crashtech/judge_queue.html", {
        "h": hackathon, "subs": subs,
        "challenges": hackathon.challenges.all(),
        "active_challenge": challenge_id,
    })


@review_required
def review_submission(request, hackathon, submission_id):
    """REQ-6.5.12: approve (award point_value, pass/fail) or reject (+feedback).
    Points count only after approval. Notifies the team (REQ-6.5.21)."""
    sub = get_object_or_404(Submission, pk=submission_id, challenge__hackathon=hackathon)
    if request.method != "POST":
        return redirect("crashtech_judge", slug=hackathon.slug)
    action = request.POST.get("action")
    from .community import notify
    if action == "approve":
        sub.status = "approved"
        sub.points_awarded = sub.challenge.point_value
        sub.feedback_note = (request.POST.get("feedback_note") or "").strip()
        verb_text = f"ההגשה שלכם ל«{sub.challenge.title}» אושרה! +{sub.points_awarded} נק'"
    elif action == "reject":
        sub.status = "rejected"
        sub.points_awarded = 0
        sub.feedback_note = (request.POST.get("feedback_note") or "").strip()
        verb_text = f"ההגשה ל«{sub.challenge.title}» נדחתה. אפשר לתקן ולהגיש מחדש."
    else:
        return redirect("crashtech_judge", slug=hackathon.slug)
    sub.reviewed_by = request.user
    sub.reviewed_at = timezone.now()
    sub.save()
    for m in sub.team.members.all():
        notify(m, verb="crashtech_review", text=verb_text,
               url=f"/crashtech/{hackathon.slug}/")
    messages.success(request, "ההגשה נשפטה.")
    return redirect("crashtech_judge", slug=hackathon.slug)


@organizer_required
def bonus_award(request, hackathon, challenge_id):
    """REQ-6.5.13: organizer-only — rank the top-N of a performance/creativity
    challenge and award bonus points per tier."""
    challenge = get_object_or_404(Challenge, pk=challenge_id, hackathon=hackathon)
    subs = (Submission.objects.filter(challenge=challenge)
            .select_related("team").order_by("-status"))
    if request.method == "POST":
        tiers = challenge.bonus_points_tiers or []
        for sub in subs:
            rank_raw = (request.POST.get(f"rank_{sub.pk}") or "").strip()
            if rank_raw.isdigit():
                rank = int(rank_raw)
                bonus = tiers[rank - 1] if 1 <= rank <= len(tiers) else 0
                sub.bonus_points_awarded = bonus
                sub.save(update_fields=["bonus_points_awarded"])
            else:
                if sub.bonus_points_awarded:
                    sub.bonus_points_awarded = 0
                    sub.save(update_fields=["bonus_points_awarded"])
        messages.success(request, "נקודות הבונוס חולקו.")
        return redirect("crashtech_manage", slug=hackathon.slug)
    return render(request, "app/crashtech/bonus.html", {
        "h": hackathon, "challenge": challenge, "subs": subs,
    })


def leaderboard(request, slug):
    """REQ-6.5.15/6.5.20: public anonymized leaderboard (approved + pending)."""
    hackathon = get_object_or_404(Hackathon, slug=slug)
    # organizer/admin see real names; everyone else sees anonymized labels
    anonymized = not can_configure(request.user, hackathon)
    rows = compute_leaderboard(hackathon, anonymized=anonymized)
    return render(request, "app/crashtech/leaderboard.html", {
        "h": hackathon, "rows": rows, "anonymized": anonymized,
    })


def qr_upload(request, token):
    """Tokenized phone upload of the demo video (no login). The token binds the
    upload to the right team+challenge (REQ-6.5.11)."""
    tok = get_object_or_404(QRToken, token=token)
    if not tok.is_valid:
        return render(request, "app/crashtech/qr_upload.html", {"expired": True})
    if not tok.challenge.hackathon.accepts_submissions:
        return render(request, "app/crashtech/qr_upload.html", {"closed": True, "tok": tok})
    if request.method == "POST" and request.FILES.get("video"):
        sub, _ = Submission.objects.get_or_create(challenge=tok.challenge, team=tok.team)
        sub.video_file = request.FILES["video"]
        sub.status = "pending"
        sub.save()
        return render(request, "app/crashtech/qr_upload.html", {"done": True, "tok": tok})
    return render(request, "app/crashtech/qr_upload.html", {"tok": tok})


# --- Glory phase (SPR-6.5.5) ---

@organizer_required
def generate_certificates(request, hackathon):
    """REQ-6.5.17: issue certificates — winner/runner-up for the top two by
    final ranking, participation for the rest. Idempotent per team."""
    if request.method != "POST":
        return redirect("crashtech_manage", slug=hackathon.slug)
    ranking = final_ranking(hackathon)
    for i, row in enumerate(ranking):
        if i == 0 and row["approved"] > 0:
            ctype = "winner"
        elif i == 1 and row["approved"] > 0:
            ctype = "runner_up"
        else:
            ctype = "participation"
        Certificate.objects.update_or_create(
            hackathon=hackathon, team=row["team"], defaults={"type": ctype})
    messages.success(request, "התעודות הונפקו.")
    return redirect("crashtech_manage", slug=hackathon.slug)


def certificate_view(request, cert_id):
    """Public, shareable certificate page (REQ-6.5.17)."""
    cert = get_object_or_404(
        Certificate.objects.select_related("hackathon", "team"), cert_id=cert_id)
    return render(request, "app/crashtech/certificate.html", {"cert": cert})


@organizer_required
def glory_edit(request, hackathon):
    """REQ-6.5.18: organizer curates highlights + photos and publishes."""
    glory, _ = GloryPage.objects.get_or_create(hackathon=hackathon)
    if request.method == "POST":
        glory.highlights = (request.POST.get("highlights") or "").strip()
        publish = request.POST.get("publish") == "on"
        if publish and not glory.published:
            glory.published_at = timezone.now()
        glory.published = publish
        glory.save()
        for img in request.FILES.getlist("photos"):
            glory.photos.create(image=img)
        messages.success(request, "עמוד התהילה נשמר.")
        return redirect("crashtech_glory", slug=hackathon.slug)
    return render(request, "app/crashtech/glory_edit.html", {"h": hackathon, "glory": glory})


def glory_page(request, slug):
    """REQ-6.5.18/6.5.20: the permanent public memorial (published only)."""
    hackathon = get_object_or_404(Hackathon, slug=slug)
    glory = getattr(hackathon, "glory_page", None)
    if glory is None or not glory.published:
        if not can_configure(request.user, hackathon):
            from django.http import Http404
            raise Http404
    # winners revealed; full final ranking with real names (event is over)
    ranking = final_ranking(hackathon)
    return render(request, "app/crashtech/glory.html", {
        "h": hackathon, "glory": glory, "ranking": ranking,
        "photos": glory.photos.all() if glory else [],
    })


@login_required
def consent_toggle(request, slug):
    """REQ-6.5.19: a team member opts in/out of Glory-Page publication."""
    hackathon = get_object_or_404(Hackathon, slug=slug)
    team = team_of(request.user, hackathon)
    if team and request.method == "POST":
        team.glory_consent = request.POST.get("glory_consent") == "on"
        team.save(update_fields=["glory_consent"])
        messages.success(request, "העדפת הפרסום עודכנה.")
    return redirect("crashtech_detail", slug=slug)


def video_gallery(request, slug):
    """REQ-6.5.20: anonymized public gallery — approved demos from teams that
    consented to publication only."""
    hackathon = get_object_or_404(Hackathon, slug=slug)
    subs = (Submission.objects.filter(
                challenge__hackathon=hackathon, status="approved",
                team__glory_consent=True)
            .exclude(video_url="", video_file="")
            .select_related("team", "challenge"))
    return render(request, "app/crashtech/gallery.html", {"h": hackathon, "subs": subs})
