"""Seed demo teachers, classes and students for the Classrooms feature (Chapter 9).

DEV-ONLY. Never wire this into the Render startCommand (production is real-data
only). Re-runnable: all demo objects use the 'demo_class_' username prefix and
get_or_create, so running twice does not duplicate. To remove, delete users with
that prefix and their classes.
"""

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.utils import timezone

from app.classroom_models import (
    ClassInvite,
    ClassJoinRequest,
    ClassMembership,
    ClassMessage,
    TeacherClass,
)
from app.models import Course, LessonModelSubmission, UserVideoProgress

PREFIX = "demo_class_"
PASSWORD = "demo12345"


class Command(BaseCommand):
    help = "Seed demo teachers/classes/students for the Classrooms feature (dev only)."

    def _user(self, suffix, display, teacher=False):
        username = PREFIX + suffix
        user, created = User.objects.get_or_create(
            username=username, defaults={"first_name": display})
        if created:
            user.set_password(PASSWORD)
            user.first_name = display
            user.save()
        prof = user.profile
        prof.display_name = display
        prof.is_teacher = teacher
        prof.save()
        return user

    def handle(self, *args, **opts):
        # Teachers
        avi = self._user("teacher_avi", "אבי המורה", teacher=True)
        dana = self._user("teacher_dana", "דנה לוי", teacher=True)

        # Students
        names = [
            ("noa", "נועה כהן"), ("yotam", "יותם בר"), ("maya", "מאיה גל"),
            ("eitan", "איתן רז"), ("shira", "שירה דן"), ("omer", "עומר אלון"),
            ("tamar", "תמר נוי"), ("daniel", "דניאל פז"),
        ]
        students = [self._user(s, d) for s, d in names]

        # A real published course to attach progress + projects to (for the roster).
        course = (Course.objects.filter(is_published=True)
                  .filter(videos__isnull=False).distinct().first())
        videos = list(course.videos.order_by("lesson_order")[:4]) if course else []

        # Class 1 - Avi, robotics, full of students with progress + projects
        c1 = self._class(avi, "כיתת רובוטיקה ז'", "נפגשים יום ג'. בונים ומשתפים פרויקטים.")
        for i, st in enumerate(students[:6]):
            ClassMembership.objects.get_or_create(
                klass=c1, student=st, defaults={"status": "active"})
            if videos:
                # Give each student some progress (more for the first few).
                for v in videos[: 1 + (i % len(videos))]:
                    UserVideoProgress.objects.update_or_create(
                        user=st, video=v,
                        defaults={"percent_watched": 100, "completed_at": timezone.now()})
                # A couple of students share a Scratch project to the class gallery.
                if i < 3:
                    LessonModelSubmission.objects.update_or_create(
                        user=st, video=videos[0],
                        defaults={"scratch_id": str(110000000 + i),
                                  "caption": f"הפרויקט של {st.first_name}"})
        # One student opts out of sharing projects.
        ClassMembership.objects.filter(klass=c1, student=students[2]).update(share_projects=False)

        # Class messages: a teacher announcement + a student discussion post.
        if not c1.messages.exists():
            ClassMessage.objects.create(
                klass=c1, author=avi, is_announcement=True,
                body="ברוכים הבאים לכיתה! השבוע נתחיל בבניית הרובוט הראשון.")
            ClassMessage.objects.create(
                klass=c1, author=students[0], is_announcement=False,
                body="איזה כיף, אני כבר מתחילה!")

        # A pending invite to a student who has not joined yet.
        ClassInvite.objects.get_or_create(
            klass=c1, invitee=students[6], defaults={"inviter": avi, "status": "pending"})

        # A directory-style join request waiting for the teacher's approval.
        ClassJoinRequest.objects.get_or_create(
            klass=c1, student=students[7],
            defaults={"status": "pending", "message": "אפשר להצטרף? אני אוהב רובוטיקה."})

        # Class 2 - Dana, smaller
        c2 = self._class(dana, "סדנת תכנות אחר הצהריים", "קבוצה קטנה, קצב נינוח.")
        for st in students[6:]:
            ClassMembership.objects.get_or_create(
                klass=c2, student=st, defaults={"status": "active"})

        self.stdout.write(self.style.SUCCESS(
            "Seeded classrooms demo:\n"
            f"  Teachers: {avi.username}, {dana.username}\n"
            f"  Classes: '{c1.name}' ({c1.member_count} students), "
            f"'{c2.name}' ({c2.member_count} students)\n"
            f"  Course used for progress/projects: {course.title if course else 'none found'}\n"
            f"  Login for any demo user with password: {PASSWORD}\n"
            f"  Try: log in as {avi.username} -> Manage '{c1.name}' to see the roster + QR."))

    def _class(self, owner, name, desc):
        klass, _ = TeacherClass.objects.get_or_create(
            owner=owner, name=name, defaults={"description": desc})
        return klass
