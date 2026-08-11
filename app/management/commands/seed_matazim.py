"""Seed the מט״צים program space (F-10.9, Chapter 10).

Idempotent and additive: creates the Program, a few schools, and optionally a
demo cohort. Re-running never overwrites an edited record, in the same spirit as
`seed_blog` - production edits win.

    python manage.py seed_matazim              # program + schools only
    python manage.py seed_matazim --demo       # + a demo cohort of members
    python manage.py seed_matazim --demo --user avi.salmon@gmail.com
"""

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.utils import timezone

from app.matazim_models import Program, ProgramMembership, School
from app.models import Course, Enrollment, UserVideoProgress, Video

PROGRAM = {
    "slug": "matazim",
    "name": "מט״צים",
    "tagline": "מובילים טכנולוגיים צעירים",
    "description": (
        "מט״צים היא תוכנית להכשרת נוער כמובילים ומדריכים טכנולוגיים, כבר בחטיבה "
        "ובתיכון. מתמיינים, לומדים, יוצרים, ואז מדריכים ילדים צעירים יותר.\n"
        "הלמידה עצמה מתרחשת ב־babook, עם מעקב התקדמות ותעודות. כאן עוקבים אחרי "
        "הדרך: איפה אתם, מה כבר השלמתם, ומה המשימה הבאה."
    ),
}

SCHOOLS = [
    ("תיכון עתיד טירת הכרמל", "טירת הכרמל"),
    ("חטיבת הביניים רעות", "חיפה"),
    ("תיכון עתיד נשר", "נשר"),
    ("חטיבת הביניים אלון", "קריית ים"),
]

# A demo cohort spread across the funnel, so every stage of the track renders.
# The last field is babook training to fake up: [(course_slug, fraction_done)].
# Without it the אזור אישי shows zeroes and proves nothing - and the whole point
# of Chapter 10 is that the record is *derived* from real babook activity
# (DEC-71), so the demo has to exercise that path.
DEMO = [
    ("matz_noa", "נועה", ProgramMembership.CERTIFIED, 0,
     [("tinkercad", 1.0), ("arduino-tinkercad", 1.0), ("scratch", 1.0), ("python", 0.4)]),
    ("matz_yotam", "יותם", ProgramMembership.PROJECT_SUBMITTED, 0,
     [("tinkercad", 1.0), ("arduino-tinkercad", 0.7)]),
    ("matz_lian", "ליאן", ProgramMembership.IN_TRAINING, 1,
     [("tinkercad", 1.0), ("scratch", 0.35)]),
    ("matz_omer", "עומר", ProgramMembership.IN_TRAINING, 2,
     [("tinkercad", 0.55)]),
    ("matz_adi", "עדי", ProgramMembership.APPLIED, 3, []),
    ("matz_leader", "מוביל בית ספר", ProgramMembership.CERTIFIED, 0,
     [("tinkercad", 1.0), ("fusion360", 1.0)]),
]


def fake_training(user, slug, fraction):
    """Mark the first `fraction` of a course's lessons as watched, and enrol.

    Writes only to the *existing* babook progress tables - the program space has
    no progress tables of its own to write to, which is the point.
    """
    course = Course.objects.filter(slug=slug).first()
    if not course:
        return None
    videos = list(Video.objects.filter(course=course).order_by("lesson_order"))
    if not videos:
        return None
    n = max(1, round(len(videos) * fraction))
    for v in videos[:n]:
        UserVideoProgress.objects.update_or_create(
            user=user, video=v,
            defaults={"percent_watched": 100.0, "quiz_passed": True,
                      "completed_at": timezone.now()})
    Enrollment.objects.update_or_create(
        user=user, course=course,
        defaults={"completed_at": timezone.now() if n >= len(videos) else None})
    return f"{slug} {n}/{len(videos)}"


class Command(BaseCommand):
    help = "Seed the מט״צים program, schools, and optionally a demo cohort."

    def add_arguments(self, parser):
        parser.add_argument("--schools", action="store_true",
                            help="Also create the sample schools (dev only: the "
                                 "names are invented).")
        parser.add_argument("--demo", action="store_true",
                            help="Also create a demo cohort of members.")
        parser.add_argument("--user", default="",
                            help="Email or username to enrol as a certified מט״צ.")

    def handle(self, *args, **opts):
        program, created = Program.objects.get_or_create(
            slug=PROGRAM["slug"], defaults=PROGRAM)
        self.stdout.write(("created " if created else "exists  ") + f"program: {program.name}")

        # Production runs this bare, and bare means the Program record and
        # nothing else. Without the record every /matazim/ page 404s, which is
        # why it belongs in the deploy; with invented school names it would put
        # fiction in front of real users, which is why they do not.
        schools = []
        if not (opts["schools"] or opts["demo"]):
            self.stdout.write(self.style.SUCCESS(
                "program ready (no sample schools; pass --schools for those)"))
            return
        for name, city in SCHOOLS:
            school, made = School.objects.get_or_create(
                program=program, name=name, defaults={"city": city})
            schools.append(school)
            self.stdout.write(("created " if made else "exists  ") + f"school: {school.name}")

        if opts["user"]:
            ident = opts["user"]
            user = (User.objects.filter(email__iexact=ident).first()
                    or User.objects.filter(username__iexact=ident).first())
            if not user:
                self.stderr.write(f"no such user: {ident}")
            else:
                m, made = ProgramMembership.objects.get_or_create(
                    user=user, program=program, cohort_year=program.current_cohort_year,
                    defaults={
                        "school": schools[0] if schools else None,
                        "school_join_status": ProgramMembership.SCHOOL_CONFIRMED,
                        "status": ProgramMembership.CERTIFIED,
                        "certified_at": timezone.now(),
                        "certification_note": "Seeded as program staff.",
                    })
                # Staff-ness lives on Program.staff, not on the membership: the
                # adults running the program are not cohort members.
                program.staff.add(user)
                self.stdout.write(
                    ("created " if made else "exists  ")
                    + f"membership: {user.username} [{m.status}] + program staff")

        if not opts["demo"]:
            return

        for username, display, status, school_i, training in DEMO:
            user, made_user = User.objects.get_or_create(
                username=username, defaults={"first_name": display})
            if made_user:
                user.set_unusable_password()
                user.save()
                profile = getattr(user, "profile", None)
                if profile:
                    profile.display_name = display
                    profile.save(update_fields=["display_name"])
            if username == "matz_leader":
                # A school leader is a teacher, not a cohort member: they get no
                # ProgramMembership at all, only a place in School.leaders.
                if schools:
                    schools[school_i].leaders.add(user)
                    self.stdout.write(f"leader:      {display} -> {schools[school_i].name}")
                continue
            m, made = ProgramMembership.objects.get_or_create(
                user=user, program=program, cohort_year=program.current_cohort_year,
                defaults={
                    "school": schools[school_i] if schools else None,
                    "school_join_status": (ProgramMembership.SCHOOL_PENDING
                                           if status == ProgramMembership.APPLIED
                                           else ProgramMembership.SCHOOL_CONFIRMED),
                    "status": status,
                    "certified_at": (timezone.now()
                                     if status == ProgramMembership.CERTIFIED else None),
                })
            done = [r for r in (fake_training(user, slug, frac)
                                for slug, frac in training) if r]
            self.stdout.write(
                ("created " if made else "exists  ")
                + f"demo member: {display} [{m.get_status_display()}]"
                + (f" | training: {', '.join(done)}" if done else ""))

        self.stdout.write(self.style.SUCCESS("seed_matazim done"))
