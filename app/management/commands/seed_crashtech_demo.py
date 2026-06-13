"""Seed a realistic CrashTech demo so the platform can be experienced end-to-end
without setting up a real event. Idempotent: with --if-empty it only seeds when
no demo exists, so it is safe to run on every deploy.

Content references Avi's real TechCrash2026 kit (Intel MAX 10 FPGA + ESP32:
LEDs, OLED, ADXL345 accelerometer, 7-seg, UART) — repo github.com/avisalmon/TechCrash2026.
"""
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.utils import timezone

REPO = "https://github.com/avisalmon/TechCrash2026"
DEMO_PREFIX = "crashtech-vlsi-demo"

CHALLENGES = [
    ("Alive Test", "מוודאים שהערכה חיה: רצף LEDים, קריאת חיישן ל-OLED, משוב כפתורים, ו-UART echo מול ה-FPGA.", 100, "pass_fail", 0, []),
    ("Internet Clock", "סנכרון שעון מול NTP ב-WiFi והצגת השעה על תצוגת 7-segment.", 150, "pass_fail", 0, []),
    ("Accelerometer Arcade", "השתמשו ב-ADXL345 (SPI) כדי לשלוט במשחק או באפקט על ה-OLED.", 200, "pass_fail", 0, []),
    ("Coolest Hack", "ההאק הכי יצירתי שמשלב FPGA + ESP32. נשפט על יצירתיות.", 0, "performance_creativity", 3, [50, 30, 10]),
]

TEAMS = [
    ("Bit Flippers", ["דנה", "יואב"]),
    ("Clock Cycles", ["מאיה", "עומר"]),
    ("Silicon Dreams", ["נועה", "איתי"]),
    ("UART Heroes", ["טל", "רוני"]),
]


class Command(BaseCommand):
    help = "Seed a demo CrashTech hackathon (live + glory). Idempotent with --if-empty."

    def add_arguments(self, parser):
        parser.add_argument("--if-empty", action="store_true",
                            help="Only seed if no demo hackathon exists yet.")

    def handle(self, *args, **opts):
        from app.models import Hackathon
        if opts["if_empty"] and Hackathon.objects.filter(slug__startswith=DEMO_PREFIX).exists():
            self.stdout.write("CrashTech demo already present — skipping.")
            return

        organizer = (User.objects.filter(is_superuser=True).first()
                     or self._demo_user("crashtech_demo_host", "מארגן הדגמה", staff=True))
        judge = self._demo_user("crashtech_demo_judge", "שופט הדגמה")

        live = self._build_event(organizer, judge, status="active",
                                 name="CrashTech VLSI 2026 (הדגמה חיה)",
                                 slug=f"{DEMO_PREFIX}-live")
        glory = self._build_event(organizer, judge, status="glory",
                                  name="CrashTech VLSI 2025 (הדגמה - תהילה)",
                                  slug=f"{DEMO_PREFIX}-glory", consent_all=True)
        self._finalize_glory(glory)
        self.stdout.write(self.style.SUCCESS(
            f"Seeded CrashTech demo: live=/crashtech/{live.slug}/ glory=/crashtech/{glory.slug}/"))

    # --- helpers ---
    def _demo_user(self, username, display, staff=False):
        u, created = User.objects.get_or_create(
            username=username, defaults={"is_staff": staff, "email": f"{username}@demo.babook.co.il"})
        if created:
            u.set_unusable_password()
            u.save()
        u.profile.display_name = display
        u.profile.is_public = True
        u.profile.save()
        return u

    def _build_event(self, organizer, judge, status, name, slug, consent_all=False):
        from app.crashtech import grant_role
        from app.models import Challenge, Hackathon, Submission, Team
        now = timezone.now()
        h, created = Hackathon.objects.get_or_create(slug=slug, defaults=dict(
            name=name, organizer=organizer, status=status,
            start_at=now - timezone.timedelta(hours=2),
            end_at=now + timezone.timedelta(hours=22),
            submission_deadline=now + timezone.timedelta(hours=22),
            team_size=3, hardware_stock=8, github_repo_url=REPO,
        ))
        if not created:
            return h
        grant_role(h, organizer, "organizer")
        grant_role(h, judge, "judge")
        chs = [Challenge.objects.create(
            hackathon=h, title=t, description=d, point_value=pv, scoring_mode=sm,
            top_submission_count=topn, bonus_points_tiers=tiers, visible=True,
            created_by=organizer) for (t, d, pv, sm, topn, tiers) in CHALLENGES]

        teams = []
        for i, (tname, members) in enumerate(TEAMS, start=1):
            team = Team.objects.create(hackathon=h, name=tname, anon_ordinal=i,
                                       hardware_status="received",
                                       glory_consent=consent_all or i <= 3)
            for j, m in enumerate(members):
                team.members.add(self._demo_user(f"demo_{slug}_{i}_{j}", m))
            teams.append(team)

        # A spread of submissions across statuses for a lively board.
        def sub(team, ch, status, pts=0, fb="", vid="dQw4w9WgXcQ"):
            return Submission.objects.create(
                challenge=ch, team=team, status=status, points_awarded=pts,
                video_url=f"https://youtu.be/{vid}", feedback_note=fb,
                reviewed_by=judge if status != "pending" else None,
                reviewed_at=now if status != "pending" else None)
        sub(teams[0], chs[0], "approved", 100)
        sub(teams[0], chs[1], "approved", 150)
        sub(teams[0], chs[3], "approved", 0)
        sub(teams[1], chs[0], "approved", 100)
        sub(teams[1], chs[1], "pending")
        sub(teams[2], chs[0], "rejected", 0, fb="הוידאו חתוך - צלמו שוב את ה-OLED בבירור.")
        sub(teams[2], chs[2], "pending")
        sub(teams[3], chs[0], "approved", 100)
        sub(teams[3], chs[3], "approved", 0)
        return h

    def _finalize_glory(self, h):
        """Award bonus, generate certificates, publish the Glory Page."""
        from app.crashtech import final_ranking
        from app.models import Certificate, Challenge, GloryPage, Submission
        perf = Challenge.objects.filter(hackathon=h, scoring_mode="performance_creativity").first()
        if perf:
            tiers = perf.bonus_points_tiers
            for rank, s in enumerate(Submission.objects.filter(challenge=perf, status="approved"), start=1):
                if rank <= len(tiers):
                    s.bonus_points_awarded = tiers[rank - 1]
                    s.save(update_fields=["bonus_points_awarded"])
        for i, row in enumerate(final_ranking(h)):
            ctype = "winner" if i == 0 else "runner_up" if i == 1 else "participation"
            Certificate.objects.update_or_create(hackathon=h, team=row["team"],
                                                 defaults={"type": ctype})
        glory, _ = GloryPage.objects.get_or_create(hackathon=h)
        glory.highlights = ("## אירוע מדהים!\n\n24 שעות של פתרונות חומרה יצירתיים - "
                            "FPGA, ESP32 והרבה קפה. תודה לכל המשתתפים והשופטים. נתראה בשנה הבאה!")
        glory.published = True
        glory.published_at = timezone.now()
        glory.save()
