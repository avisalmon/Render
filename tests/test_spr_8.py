"""EPIC-8 — Admin / Management Control Dashboard.

Covers SPR-8.1 (foundation & access), SPR-8.2 (users & training),
SPR-8.3 (cost & spend), SPR-8.4 (engagement), SPR-8.5 (system),
SPR-8.6 (alerts). Every test traces to a REQ-8.x / F-8.x.
"""

import pytest
from django.contrib.auth.models import User
from django.test import Client
from django.utils import timezone

from app.models import (
    AlertEvent,
    AlertRule,
    ChatSession,
    ContentReport,
    CorporateLead,
    CostRecord,
    Course,
    CourseCertificate,
    DashboardSnapshot,
    Enrollment,
    NewsletterSubscriber,
    UsageLog,
    UserVideoProgress,
    Video,
)

DASH = "/admin-dashboard/"


# --------------------------------------------------------------------------- helpers
def _user(name="m", **flags):
    u = User.objects.create_user(name, password="p", email=f"{name}@x.com")
    for k, v in flags.items():
        setattr(u, k, v)
    u.save()
    return u


def _super(name="root"):
    return User.objects.create_superuser(name, f"{name}@x.com", "p")


def _client(u):
    c = Client()
    c.force_login(u)
    return c


def _course(slug="c1", title="קורס", published=True):
    return Course.objects.create(title=title, slug=slug, is_published=published)


# =========================================================================== SPR-8.1
@pytest.mark.django_db
def test_anonymous_routed_to_join():
    """REQ-8.1.2 / F-8.1.1 — anonymous → /join/ wall, never a bare page."""
    resp = Client().get(DASH)
    assert resp.status_code == 302
    assert "/join/" in resp.url


@pytest.mark.django_db
def test_staff_forbidden():
    """REQ-8.1.2 — staff (non-superuser) cannot reach the dashboard."""
    staff = _user("s", is_staff=True)
    resp = _client(staff).get(DASH)
    assert resp.status_code == 403


@pytest.mark.django_db
def test_superuser_ok():
    """REQ-8.1.1/8.1.2 — superuser gets the hub."""
    resp = _client(_super()).get(DASH)
    assert resp.status_code == 200
    assert "לוח בקרה ניהולי" in resp.content.decode()


@pytest.mark.django_db
def test_nav_link_superuser_only():
    """F-8.1.1 — the ניהול nav link shows only to superusers."""
    assert "admin-dashboard" in _client(_super()).get("/").content.decode()
    assert "admin-dashboard" not in _client(_user("s2", is_staff=True)).get("/").content.decode()


@pytest.mark.django_db
def test_snapshot_and_cost_models():
    """REQ-8.1.3 — snapshot + cost record persist."""
    DashboardSnapshot.objects.create(scope="system", metrics={"x": 1})
    CostRecord.objects.create(service="openai", period="2026-06", amount_usd=3, source="live")
    assert DashboardSnapshot.objects.count() == 1
    assert CostRecord.objects.get(service="openai").amount_usd == 3


@pytest.mark.django_db
def test_capture_command_creates_snapshots():
    """REQ-8.1.4 / F-8.1.4 — the nightly command captures all sections."""
    from django.core.management import call_command

    call_command("capture_dashboard_snapshot")
    scopes = set(DashboardSnapshot.objects.values_list("scope", flat=True))
    assert {"users_training", "engagement", "system", "all"} <= scopes
    assert CostRecord.objects.exists()  # adapters ran


@pytest.mark.django_db
def test_refresh_section_post():
    """REQ-8.1.5 / F-8.1.5 — per-section refresh creates a fresh snapshot."""
    c = _client(_super())
    before = DashboardSnapshot.objects.filter(scope="system").count()
    resp = c.post("/admin-dashboard/refresh/system/")
    assert resp.status_code == 302
    assert DashboardSnapshot.objects.filter(scope="system").count() == before + 1


@pytest.mark.django_db
def test_range_selector():
    """REQ-8.1.6 — range param is accepted."""
    resp = _client(_super()).get(DASH + "?range=7")
    assert resp.status_code == 200


# =========================================================================== SPR-8.2
@pytest.mark.django_db
def test_users_training_metrics():
    """REQ-8.2.1/8.2.3/8.2.4 / F-8.2.* — counts + popular-course ranking."""
    from app.dashboard.metrics import collect_users_training

    c1, c2 = _course("a", "Alpha"), _course("b", "Beta")
    v1 = Video.objects.create(course=c1, title="L1", duration_seconds=600, lesson_order=1)
    learners = [_user(f"u{i}") for i in range(3)]
    for u in learners:
        Enrollment.objects.create(user=u, course=c1)
    Enrollment.objects.create(user=learners[0], course=c2)
    Enrollment.objects.filter(user=learners[0], course=c1).update(completed_at=timezone.now())
    UserVideoProgress.objects.create(
        user=learners[0],
        video=v1,
        percent_watched=100,
        quiz_passed=True,
        completed_at=timezone.now(),
    )
    CourseCertificate.objects.create(user=learners[0], course=c1)

    m = collect_users_training(30)
    assert m["enrollments"] == 4
    assert m["certificates"] == 1
    assert m["watch_hours"] > 0
    # Alpha has more enrollments than Beta → ranked first
    assert m["popular_courses"][0]["title"] == "Alpha"
    assert m["popular_courses"][0]["enrollments"] == 3


@pytest.mark.django_db
def test_activation_and_corporate_funnels():
    """REQ-8.2.5/8.2.6 — funnels derive from local models."""
    from app.dashboard.metrics import collect_users_training

    CorporateLead.objects.create(name="Acme", message="hi", status="new")
    NewsletterSubscriber.objects.create(email="a@b.com", confirmed_at=timezone.now())
    NewsletterSubscriber.objects.create(email="c@d.com")  # pending
    m = collect_users_training(30)
    assert m["leads_total"] == 1
    assert m["subs_confirmed"] == 1
    assert m["subs_pending"] == 1
    assert "registered" in m["funnel"]


# =========================================================================== SPR-8.3
@pytest.mark.django_db
def test_cost_adapters_run_all():
    """REQ-8.3.1/8.3.2 / F-8.3.* — every adapter yields a CostRecord."""
    from app.dashboard.cost_adapters import ADAPTERS, run_all_adapters

    rows = run_all_adapters("2026-06")
    services = {r.service for r in rows}
    assert services == {a.service for a in ADAPTERS}


@pytest.mark.django_db
def test_openai_adapter_live_from_usagelog():
    """REQ-8.3.3 — OpenAI cost comes live from UsageLog."""
    from app.dashboard.cost_adapters import OpenAICostAdapter

    u = _user("payer")
    sess = ChatSession.objects.create(user=u)
    UsageLog.objects.create(
        user=u,
        session=sess,
        model="gpt-4o-mini",
        prompt_tokens=100,
        completion_tokens=50,
        cost_usd=1.25,
    )
    period = timezone.now().strftime("%Y-%m")
    amount, source, note, raw = OpenAICostAdapter().fetch(period)
    assert source == "live"
    assert float(amount) == pytest.approx(1.25)


@pytest.mark.django_db
def test_manual_cost_override_preserved():
    """REQ-8.3.11 — a manual override is not clobbered by adapters."""
    from app.dashboard.cost_adapters import run_all_adapters, set_manual_cost

    set_manual_cost("render", "2026-06", 25, "hosting")
    run_all_adapters("2026-06")
    rec = CostRecord.objects.get(service="render", period="2026-06")
    assert rec.source == "manual"
    assert float(rec.amount_usd) == 25


@pytest.mark.django_db
def test_manual_cost_view():
    """REQ-8.3.11 / F-8.3.11 — the manual-entry endpoint saves an override."""
    resp = _client(_super()).post(
        "/admin-dashboard/cost/manual/",
        {"service": "domain", "amount": "12.5", "note": "yr", "period": "2026-06"},
    )
    assert resp.status_code == 302
    assert float(CostRecord.objects.get(service="domain").amount_usd) == 12.5


# =========================================================================== SPR-8.4
@pytest.mark.django_db
def test_engagement_metrics():
    """REQ-8.4.1/8.4.2/8.4.4 — engagement breadth + moderation pulse."""
    from app.dashboard.metrics import collect_engagement

    reporter = _user("rep")
    ContentReport.objects.create(
        reporter=reporter, content_type="thread", object_id=1, reason="spam", status="open"
    )
    m = collect_engagement(7)
    assert m["open_reports"] == 1
    assert "active_contributors" in m
    assert "engagement_rate_pct" in m


# =========================================================================== SPR-8.5
@pytest.mark.django_db
def test_system_metrics():
    """REQ-8.5.3/8.5.4 — system section reports db/storage/deps."""
    from app.dashboard.metrics import collect_system

    m = collect_system()
    assert "db_bytes" in m
    assert "dependencies" in m
    assert set(m["dependencies"]) == {"openai", "bunny", "resend"}


# =========================================================================== SPR-8.6
@pytest.mark.django_db
def test_alert_fires_and_notifies():
    """REQ-8.6.1 / F-8.6.1 — threshold breach raises an alert + notifies admin."""
    from app.dashboard.alerts import ensure_default_rules, evaluate_alerts
    from app.models import Notification

    admin = _super()
    ensure_default_rules()
    AlertRule.objects.filter(key="report_queue").update(threshold=1)
    rep = _user("rr")
    for i in range(2):
        ContentReport.objects.create(
            reporter=rep, content_type="thread", object_id=i, reason="x", status="open"
        )
    created = evaluate_alerts()
    assert any(e.rule_key == "report_queue" for e in created)
    assert AlertEvent.objects.filter(rule_key="report_queue", dismissed_at__isnull=True).exists()
    assert Notification.objects.filter(user=admin, verb="dashboard_alert").exists()


@pytest.mark.django_db
def test_alert_dedup():
    """REQ-8.6.1 — a still-active alert is not duplicated."""
    from app.dashboard.alerts import ensure_default_rules, evaluate_alerts

    _super()
    ensure_default_rules()
    AlertRule.objects.filter(key="report_queue").update(threshold=1)
    rep = _user("rr2")
    ContentReport.objects.create(
        reporter=rep, content_type="thread", object_id=1, reason="x", status="open"
    )
    ContentReport.objects.create(
        reporter=rep, content_type="thread", object_id=2, reason="x", status="open"
    )
    evaluate_alerts()
    evaluate_alerts()
    assert AlertEvent.objects.filter(rule_key="report_queue").count() == 1


@pytest.mark.django_db
def test_dismiss_alert():
    """REQ-8.6.2 — dismissing clears the active alert."""
    ev = AlertEvent.objects.create(rule_key="report_queue", message="x", value=5, threshold=1)
    resp = _client(_super()).post(f"/admin-dashboard/alerts/{ev.pk}/dismiss/")
    assert resp.status_code == 302
    ev.refresh_from_db()
    assert ev.dismissed_at is not None


@pytest.mark.django_db
def test_alert_config_post():
    """REQ-8.6.3 — thresholds are admin-editable."""
    from app.dashboard.alerts import ensure_default_rules

    ensure_default_rules()
    c = _client(_super())
    resp = c.post(
        "/admin-dashboard/alerts/config/",
        {
            "threshold_spend_total": "250",
            "enabled_spend_total": "on",
        },
    )
    assert resp.status_code == 302
    assert AlertRule.objects.get(key="spend_total").threshold == 250


@pytest.mark.django_db
def test_alert_config_requires_superuser():
    """REQ-8.1.2 — config page is superuser-only too."""
    resp = _client(_user("s3", is_staff=True)).get("/admin-dashboard/alerts/config/")
    assert resp.status_code == 403
