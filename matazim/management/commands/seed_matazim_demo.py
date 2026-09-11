"""A whole imaginary מט״צים, so the screens can be judged on real-looking data.

    python manage.py seed_matazim_demo            # build it
    python manage.py seed_matazim_demo --purge    # take it away again

Avi wants to see how the views look with people in them rather than with one
test row. Empty screens and screens holding a single row both lie: they hide the
scanning problem, the long-name problem, and the "which of these needs me today"
problem, which are the only things a roster is really judged on.

**Every address is on `demo.invalid`.** That is not decoration. `.invalid` is
reserved by RFC 2606 and can never resolve, so no message to one of these people
can leave the building even if a future sprint starts sending mail on assignment
(REQ-M.90). It is also what `--purge` matches on, which means the purge can
never reach a real account: it does not select by name, or by a flag someone
might forget to set, but by a domain that no real person can hold.

The people are deliberately spread across every state the product has, because
a demo where everyone is halfway through tells you nothing about how the screen
handles the ones who have not started and the ones who are finished.
"""

import random

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

DOMAIN = "demo.invalid"
PASSWORD = "matazim-demo-2026"

MANAGER = ("נעמי דמו", "naomi")

LEADERS = [
    ("רונית אלגרבלי", "ronit", "עתיד רמלה", ["ט1", "ט3"]),
    ("יוסי בן חמו", "yossi", "אורט לוד", ["ט2"]),
    ("מיכל שטרן", "michal", "הראל מודיעין", ["ט1", "ט2"]),
]

# name, fraction of scratch done, fraction of advanced done, certificates, state
#
# Fractions rather than lesson counts, because the real courses are 19 and 15
# lessons and hard-coded numbers produced a "certified" student reading 12/34.
# A demo that contradicts itself on the first row is worse than no demo: you
# stop trusting the screen instead of judging it.
STUDENTS = [
    ("יובל בן ארצי לוינשטיין", 1.0, 1.0, ["scratch", "scratch-advanced"], "certified"),
    ("מאיה לוי", 1.0, 1.0, ["scratch", "scratch-advanced"], "ready"),
    ("עומר שלום", 1.0, 0.5, ["scratch"], "training"),
    ("נועה כהן", 0.6, 0.0, [], "training"),
    ("איתי פרץ", 0.2, 0.0, [], "training"),
    ("שירה אברהם", 0.0, 0.0, [], "training"),
    ("דניאל אזולאי", 1.0, 1.0, ["scratch", "scratch-advanced"], "certified"),
    ("תמר גולן", 0.9, 0.1, ["scratch"], "training"),
    ("אורי מזרחי", 0.1, 0.0, [], "training"),
    ("ליאם דהן", 0.3, 0.0, [], "waiting"),
    ("רוני שביט", 0.0, 0.0, [], "waiting"),
    ("אלמה יצחקי", 1.0, 0.3, ["scratch"], "training"),
]


class Command(BaseCommand):
    help = "Seed (or purge) an imaginary מט״צים world for judging the screens."

    def add_arguments(self, parser):
        parser.add_argument("--purge", action="store_true", help="delete the demo world")

    def handle(self, *args, **options):
        if options["purge"]:
            return self._purge()
        self._seed()

    # ------------------------------------------------------------------ purge

    def _purge(self):
        """Matched by domain, so this can never reach a real person."""
        doomed = User.objects.filter(email__iendswith=f"@{DOMAIN}")
        n = doomed.count()
        doomed.delete()  # cascades into MemberProfile, Leader, Student
        self.stdout.write(self.style.SUCCESS(f"removed {n} demo accounts"))

    # ------------------------------------------------------------------- seed

    def _user(self, name, handle):
        from app.models import UserProfile

        email = f"{handle}@{DOMAIN}"
        user, created = User.objects.get_or_create(username=email, defaults={"email": email})
        if created:
            user.set_password(PASSWORD)
            user.email = email
            user.save()
        UserProfile.objects.update_or_create(user=user, defaults={"display_name": name})
        return user

    @transaction.atomic
    def _seed(self):
        from app.models import Course, CourseCertificate, UserVideoProgress
        from matazim.models import Leader, LeaderInvite, MemberProfile, Student, StudyClass

        random.seed(4417)  # the same world every time, so screenshots compare
        now = timezone.now()
        year = now.year

        courses = {
            c.slug: c for c in Course.objects.filter(slug__in=("scratch", "scratch-advanced"))
        }
        if len(courses) < 2:
            self.stdout.write(
                self.style.WARNING(
                    "scratch and scratch-advanced are not both in this database; "
                    "progress bars will read 0/0"
                )
            )

        # The program manager.
        manager = self._user(*MANAGER)
        MemberProfile.objects.update_or_create(
            user=manager,
            defaults={
                "is_program_manager": True,
                "birth_year": year - 41,
                "welcome_accepted_at": now,
            },
        )

        # Her leaders, each with classes in their own school.
        leaders = []
        for name, handle, school, class_names in LEADERS:
            user = self._user(name, handle)
            MemberProfile.objects.update_or_create(
                user=user, defaults={"birth_year": year - 38, "welcome_accepted_at": now}
            )
            leader, _ = Leader.objects.get_or_create(
                user=user,
                defaults={
                    "assigned_by": manager,
                    # REQ-M.88 and M.93 — owned by her, and actually approved.
                    # An unapproved leader is a candidate and reaches nothing.
                    "program_manager": manager,
                    "approved_at": now,
                    "approved_by": manager,
                },
            )
            classes = [
                StudyClass.objects.get_or_create(
                    leader=leader, name=cn, defaults={"school_name": school}
                )[0]
                for cn in class_names
            ]
            leaders.append((leader, classes))

        # The teenagers, spread across every state the product has.
        for i, (name, part_scratch, part_adv, certs, state) in enumerate(STUDENTS):
            user = self._user(name, f"kid{i + 1}")
            MemberProfile.objects.update_or_create(
                user=user,
                defaults={
                    "entered_via_matazim": True,
                    "welcome_accepted_at": now,
                    "entrance_test_passed_at": now,
                    "birth_year": year - 14,
                    # REQ-M.84 — without this they cannot join a leader at all,
                    # which would make the whole demo an empty roster.
                    "guardian_name": "הורה לדוגמה",
                    "guardian_email": f"parent{i + 1}@{DOMAIN}",
                    "guardian_consent_at": now,
                },
            )

            leader, classes = leaders[i % len(leaders)]
            student, _ = Student.objects.get_or_create(user=user, cohort_year=year)

            if state == "waiting":
                # Asked, not yet accepted (REQ-M.10). The leader's queue.
                student.leader = None
                student.pending_leader = leader
                student.status = Student.APPLIED
            else:
                student.leader = leader
                student.pending_leader = None
                student.status = Student.CERTIFIED if state == "certified" else Student.IN_TRAINING
                if state == "certified":
                    student.certified_at = now
                    student.certified_by = leader.user
            student.save()
            if student.leader:
                student.classes.set([random.choice(classes)])

            for slug, part in (("scratch", part_scratch), ("scratch-advanced", part_adv)):
                course = courses.get(slug)
                if not course:
                    continue
                count = round(course.videos.count() * part)
                for video in course.videos.order_by("lesson_order")[:count]:
                    UserVideoProgress.objects.update_or_create(
                        user=user,
                        video=video,
                        defaults={
                            "percent_watched": 100.0,
                            "quiz_passed": True,
                            "completed_at": now,
                        },
                    )
            for slug in certs:
                # A certificate always implies the course was finished, so the
                # lesson rows are forced to agree rather than trusting the table
                # above to have been edited consistently.
                course = courses.get(slug)
                if not course:
                    continue
                for video in course.videos.all():
                    UserVideoProgress.objects.update_or_create(
                        user=user,
                        video=video,
                        defaults={
                            "percent_watched": 100.0,
                            "quiz_passed": True,
                            "completed_at": now,
                        },
                    )
                CourseCertificate.objects.get_or_create(user=user, course=course)

        # One candidate and two live invitations, so the states Avi described are
        # visible on her screen rather than only described in a spec.
        hopeful = self._user("דנה מועמדת", "dana")
        MemberProfile.objects.update_or_create(
            user=hopeful, defaults={"birth_year": year - 35, "welcome_accepted_at": now}
        )
        Leader.objects.get_or_create(
            user=hopeful, defaults={"program_manager": manager, "is_active": True}
        )
        LeaderInvite.objects.get_or_create(
            program_manager=manager,
            kind=LeaderInvite.OPEN,
            defaults={"label": "חדר מורים אורט לוד"},
        )
        LeaderInvite.objects.get_or_create(
            program_manager=manager,
            kind=LeaderInvite.PERSONAL,
            label="שירה מהראל מודיעין",
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"seeded 1 program manager, {len(LEADERS)} leaders, 1 candidate, "
                f"{len(STUDENTS)} students, 2 invites"
            )
        )
        self.stdout.write("")
        self.stdout.write("sign in with any of these, password: " + PASSWORD)
        self.stdout.write(f"  program manager  {MANAGER[1]}@{DOMAIN}")
        for _name, handle, school, _cn in LEADERS:
            self.stdout.write(f"  leader           {handle}@{DOMAIN}   ({school})")
        self.stdout.write(f"  student          kid1@{DOMAIN}")
