"""The REST API for מט״צים (REQ-M.134, REQ-M.139, methodology Rule 6).

Full documented CRUD over every model in this app, one `ModelViewSet` each,
registered on a router under `/matazim/api/`. DRF's browsable API is the
documentation, which is the call this site already made for ustrip.

**Every queryset comes from `matazim/access.py`, and that is the point of the
whole file.** §4.4 says scope is a property of the data rather than a rule
anybody remembers. An API that derived its own scope would be a second answer to
"who may see this", free to drift from the one the screens use, and the drift
stays invisible until somebody reads another institution's child's words. So
`Scoped.get_queryset` calls one function and there is nowhere else to put a
filter.

**Some verbs are refused, and the refusal is a requirement rather than a gap.**
Rule 6 asks for real CRUD instead of the couple of verbs a screen happens to
need. It does not ask for a way around rules this product already has:
`StatusLog` and `Feedback` are append-only, a certificate is issued and revoked
rather than deleted, a retry is a new attempt rather than an edit, and נעמי's
request text is hers. Where a verb is forbidden, the mixins below say so in
words and a test holds each one. `docs/matazim/data_model.md` §5 lists them all
in one table so nobody has to find out by trying.

Written 2026-09-14, when Avi stopped feature work to bring this app onto the
methodology's principles. The community module (SPR-M.32) was the first with an
API; this is the other seventeen models.
"""

from django.utils import timezone
from rest_framework import mixins, permissions, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.response import Response

from . import access
from .models import (
    Application,
    Institution,
    EntranceAttempt,
    EntranceTarget,
    Event,
    Feedback,
    Leader,
    LeaderInvite,
    MatazCertificate,
    MemberProfile,
    Notification,
    Post,
    Request,
    RequestMessage,
    RetentionRun,
    StatusLog,
    Student,
    StudyClass,
    Submission,
    TeachingSession,
)
from .serializers import (
    ApplicationSerializer,
    InstitutionSerializer,
    EntranceAttemptSerializer,
    EntranceTargetSerializer,
    EventSerializer,
    FeedbackSerializer,
    LeaderInviteSerializer,
    LeaderSerializer,
    MatazCertificateSerializer,
    MemberProfileSerializer,
    NotificationSerializer,
    PostSerializer,
    RequestMessageSerializer,
    RequestSerializer,
    RetentionRunSerializer,
    StatusLogSerializer,
    StudentSerializer,
    StudyClassSerializer,
    SubmissionSerializer,
    TeachingSessionSerializer,
)

# --------------------------------------------------------------- foundations


class IsSignedIn(permissions.BasePermission):
    """The floor. Nothing in this app is readable by a stranger through the API.

    The public surfaces of מט״צים are pages, not endpoints: the events page, the
    certificate verification page, the recruitment sections. Each of those has a
    view that decides exactly what a stranger may see, and none of them needs a
    queryset handed to an anonymous client.
    """

    def has_permission(self, request, view):
        return bool(getattr(request.user, "is_authenticated", False))


class IsProgramManager(permissions.BasePermission):
    message = "רק מנהל/ת התוכנית."

    def has_permission(self, request, view):
        return access.is_program_manager(request.user)


class IsInTheProgramme(permissions.BasePermission):
    """Signed in and belonging to an institution.

    A candidate is signed in and belongs to nobody yet (REQ-M.99), so they get
    the same answer here as on the screen: not yours yet.
    """

    message = "הקהילה נפתחת כשמצטרפים לתוכנית."

    def has_permission(self, request, view):
        if not getattr(request.user, "is_authenticated", False):
            return False
        return access.institution_of(request.user) is not None


class Scoped(viewsets.ModelViewSet):
    """Base for every viewset here: the queryset is `access.<scope>(user)`.

    Subclasses set `scope` to the function and never override `get_queryset` to
    add a filter of their own. If a subclass needs a different set of rows, the
    place to change it is `access.py`, so the screens change with it.
    """

    permission_classes = [IsSignedIn]
    scope = None

    def get_queryset(self):
        assert self.scope is not None, "a viewset here must name its access scope"
        return self.scope(self.request.user)


class ReadOnlyScoped(
    mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet
):
    """Readable, never written through the API.

    A refused verb here returns 405, which is the honest answer: the route
    exists and that method is not part of it. What it must never be is a verb
    that quietly succeeds and breaks a rule somewhere else.
    """

    permission_classes = [IsSignedIn]
    scope = None

    def get_queryset(self):
        assert self.scope is not None
        return self.scope(self.request.user)


class NoDeleteMixin:
    def destroy(self, request, *args, **kwargs):
        raise PermissionDenied(self.delete_refusal)


class NoUpdateMixin:
    def update(self, request, *args, **kwargs):
        raise PermissionDenied(self.update_refusal)

    def partial_update(self, request, *args, **kwargs):
        raise PermissionDenied(self.update_refusal)


class InstitutionViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin,
                          mixins.UpdateModelMixin, viewsets.GenericViewSet):
    """REQ-M.139, REQ-M.143 — the tenancy root, readable and renameable by its
    own managers.

    No create, no delete: there is no screen that makes a second institution
    yet, and a POST here would be exactly the kind of quiet capability Rule 6
    warns against building before it is asked for. `managers` is read-only in
    the serializer, so an update can only ever be the name.
    """

    serializer_class = InstitutionSerializer
    scope = staticmethod(access.visible_institutions)
    permission_classes = [IsProgramManager]

    def get_queryset(self):
        return self.scope(self.request.user)


# --------------------------------------------------------- people and roles


class MemberProfileViewSet(NoDeleteMixin, Scoped):
    """REQ-M.84, REQ-M.85 — a person's own row, and the people they run.

    Deleting a profile through here is refused because deleting a person's
    record is REQ-M.86's job: `delete_me` removes everything in one deliberate
    act the person themselves asks for, with their email typed. A DELETE on one
    row would leave the student, the submissions and the certificate behind and
    orphan them.
    """

    serializer_class = MemberProfileSerializer
    scope = staticmethod(access.visible_members)
    delete_refusal = "מחיקת חשבון נעשית במסך 'המידע שלי', כדי שלא יישארו שאריות."

    def perform_update(self, serializer):
        target = serializer.instance
        me = self.request.user
        # Guardian details may be entered by the person themselves or recorded
        # by staff who collected them on paper (REQ-M.85). Everything else about
        # somebody else's profile is not a staff member's to edit.
        if target.user_id != me.id and not access.is_program_manager(me):
            raise PermissionDenied("אפשר לערוך רק את הפרופיל שלכם.")
        recorder = me if target.user_id != me.id else None
        serializer.save(
            **({"guardian_consent_recorded_by": recorder} if recorder else {})
        )


class LeaderViewSet(Scoped):
    """REQ-M.88, REQ-M.93 — the leaders in your world.

    `institution` is stamped from whoever creates the row, which is what
    makes a leader belong to an institution at all (§4.4), and approval is an
    act by a person rather than a default: a created row is unapproved, and
    `leader_of()` refuses an unapproved row, so a leader created here grants
    nothing until somebody says yes through `approve`.
    """

    serializer_class = LeaderSerializer
    scope = staticmethod(access.visible_leaders)
    permission_classes = [IsProgramManager]

    def perform_create(self, serializer):
        from django.contrib.auth.models import User as AuthUser

        user_id = serializer.validated_data.pop("user_id", None)
        person = AuthUser.objects.filter(pk=user_id).first() if user_id else None
        if person is None:
            # Refused in words rather than crashing on a NOT NULL. A leader is
            # made out of an account that already exists; nothing here invents
            # one, which is the lesson `staff_admins` learned from the other
            # side: a typo must never conjure a record holding a role.
            raise ValidationError(
                {"user_id": "צריך חשבון קיים. אפשר להוסיף רק מי שכבר נרשם לאתר."}
            )
        if Leader.objects.filter(user=person).exists():
            raise ValidationError({"user_id": "כבר יש למשתמש/ת הזה/הזאת רשומת מוביל/ה."})

        serializer.save(
            user=person,
            institution=access.institution_of(self.request.user),
            assigned_by=self.request.user,
        )

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        """REQ-M.93 — somebody says yes, and it is recorded who and when."""
        leader = self.get_object()
        if leader.approved_at is None:
            leader.approved_at = timezone.now()
            leader.approved_by = request.user
            leader.save(update_fields=["approved_at", "approved_by"])
        return Response(LeaderSerializer(leader).data)


class StudyClassViewSet(Scoped):
    """REQ-M.24 — a leader's groups."""

    serializer_class = StudyClassSerializer
    scope = staticmethod(access.visible_classes)

    def perform_create(self, serializer):
        leader = access.leader_of(self.request.user)
        given = serializer.validated_data.get("leader")
        if leader is not None and (given is None or given.pk == leader.pk):
            serializer.save(leader=leader)
            return
        # A program manager may create a class for one of their own leaders.
        if given is not None and access.visible_leaders(self.request.user).filter(
            pk=given.pk
        ).exists():
            serializer.save()
            return
        raise PermissionDenied("אפשר ליצור כיתה רק למוביל/ה שלכם.")


class StudentViewSet(NoDeleteMixin, Scoped):
    """§4.4, §4.7 — the teenagers, and the one way their stage changes.

    `status` is not a writable field (see `serializers.py`), and this is the
    reason: a stage change has to write its `StatusLog` row in the same breath,
    or the record of who decided disappears. `set_status` is that door.
    """

    serializer_class = StudentSerializer
    scope = staticmethod(access.visible_students)
    delete_refusal = (
        "מט״צ לא נמחק/ת. יציאה מהתוכנית היא שינוי סטטוס, שנשמר עם מי שהחליט ומתי."
    )

    @action(detail=True, methods=["post"])
    def set_status(self, request, pk=None):
        """REQ-M.21, §4.7 — through `history.set_status`, which logs it."""
        from .history import set_status

        student = self.get_object()
        to = (request.data.get("status") or "").strip()
        valid = {key for key, _label in Student.STATUS_CHOICES}
        if to not in valid:
            raise ValidationError({"status": f"לא סטטוס מוכר. אפשרויות: {sorted(valid)}"})

        set_status(
            student, to, by=request.user, note=(request.data.get("note") or "").strip()
        )
        student.refresh_from_db()
        return Response(StudentSerializer(student).data)


# --------------------------------------------------------- the entrance test


class EntranceTargetViewSet(Scoped):
    """REQ-M.55, REQ-M.62 — the bank, and retiring an object from it.

    Retiring rather than deleting, because the attempts that referenced a target
    stay readable and a retired object can come back.
    """

    serializer_class = EntranceTargetSerializer
    scope = staticmethod(access.visible_targets)
    permission_classes = [IsProgramManager]

    @action(detail=True, methods=["post"])
    def retire(self, request, pk=None):
        target = self.get_object()
        target.is_retired = True
        target.retired_by = request.user
        target.retired_at = timezone.now()
        target.save(update_fields=["is_retired", "retired_by", "retired_at"])
        return Response(EntranceTargetSerializer(target).data)

    @action(detail=True, methods=["post"])
    def restore(self, request, pk=None):
        target = self.get_object()
        target.is_retired = False
        target.retired_by = None
        target.retired_at = None
        target.save(update_fields=["is_retired", "retired_by", "retired_at"])
        return Response(EntranceTargetSerializer(target).data)


class EntranceAttemptViewSet(ReadOnlyScoped):
    """REQ-M.53, REQ-M.80 — read-only, and the file is not here.

    A retry is a new row rather than an edit, because the history is the point:
    somebody who missed, read the feedback and came back has shown more of what
    this programme selects for than somebody who passed first time. Editing one
    would rewrite that, and deleting one would erase it. Creating one is the
    upload flow, which measures the model before it decides anything.
    """

    serializer_class = EntranceAttemptSerializer
    scope = staticmethod(access.visible_attempts)


# ------------------------------------------------------------------- joining


class LeaderInviteViewSet(NoUpdateMixin, Scoped):
    """REQ-M.91, REQ-M.92 — invitations, and revoking one.

    Not editable: an invitation that has been sent is a thing somebody is
    holding, and changing what it means underneath them is worse than issuing a
    new one. Revoking is the honest verb, and it is reversible by issuing again.
    """

    serializer_class = LeaderInviteSerializer
    scope = staticmethod(access.visible_invites)
    permission_classes = [IsProgramManager]
    update_refusal = "הזמנה שנשלחה לא נערכת. אפשר לבטל ולהנפיק חדשה."

    def perform_create(self, serializer):
        serializer.save(institution=access.institution_of(self.request.user))

    @action(detail=True, methods=["post"])
    def revoke(self, request, pk=None):
        invite = self.get_object()
        if invite.revoked_at is None:
            invite.revoked_at = timezone.now()
            invite.save(update_fields=["revoked_at"])
        return Response(LeaderInviteSerializer(invite).data)


class ApplicationViewSet(Scoped):
    """REQ-M.16 — what somebody wrote when they asked to join."""

    serializer_class = ApplicationSerializer
    scope = staticmethod(access.visible_applications)

    def perform_create(self, serializer):
        student = Student.objects.filter(user=self.request.user).first()
        if student is None:
            raise PermissionDenied("רק מי שנרשם/ה לתוכנית יכול/ה לבקש להצטרף למוביל/ה.")
        serializer.save(student=student)

    def perform_update(self, serializer):
        if serializer.instance.student.user_id != self.request.user.id:
            raise PermissionDenied("אפשר לערוך רק את הבקשה שלכם.")
        serializer.save()


# -------------------------------------------------------- record of decisions


class StatusLogViewSet(ReadOnlyScoped):
    """REQ-M.21, §4.7 — append-only, and written only by `history.set_status`.

    Every other record here answers "what is true now". This one answers "who
    decided, and when", and a history somebody can edit is the same as no
    history. Write it through `StudentViewSet.set_status`.
    """

    serializer_class = StatusLogSerializer
    scope = staticmethod(access.visible_status_logs)


class MatazCertificateViewSet(ReadOnlyScoped):
    """REQ-M.20, REQ-M.78 — issued by a person, revoked rather than deleted.

    Read-only here and not out of caution: `certification.certify` copies the
    name and the awarding name onto the row at the moment of issue, so a
    certificate created through a generic POST would be a document about a
    moment that never happened. Revoking is on the screen a person uses.
    """

    serializer_class = MatazCertificateSerializer
    scope = staticmethod(access.visible_certificates)


class RetentionRunViewSet(ReadOnlyScoped):
    """REQ-M.87 — the record of an approved deletion. Never written here.

    Retention runs behind a person's review rather than on a timer, because
    deletion is the one action in this product where an unattended bug is
    irreversible. A POST that created one of these rows would be a claim that a
    review happened.
    """

    serializer_class = RetentionRunSerializer
    scope = staticmethod(access.visible_retention_runs)
    permission_classes = [IsProgramManager]


# ----------------------------------------------- the work, and the feedback


class SubmissionViewSet(Scoped):
    """REQ-M.19, REQ-M.123, REQ-M.124 — work handed in, and the answer to it.

    The two decisions are actions rather than a writable `status`, because
    REQ-M.124 refuses to send work back without words: "החזרה בלי מילים אומרת
    למי שכתב אותה שהוא נכשל, ולא מה לעשות." A bare field write has no words in
    it, so the field is read-only and `send_back` requires them.
    """

    serializer_class = SubmissionSerializer
    scope = staticmethod(access.visible_submissions)

    def perform_create(self, serializer):
        student = Student.objects.filter(user=self.request.user).first()
        if student is None:
            raise PermissionDenied("רק מט״צ/ית בתוכנית מגיש/ה עבודה.")
        serializer.save(student=student, leader=student.leader)

    def perform_update(self, serializer):
        if serializer.instance.student.user_id != self.request.user.id:
            raise PermissionDenied("אפשר לערוך רק את ההגשה שלכם.")
        serializer.save()

    def perform_destroy(self, instance):
        if instance.student.user_id != self.request.user.id:
            raise PermissionDenied("הגשה של מישהו אחר לא נמחקת.")
        instance.delete()

    def _decide(self, request, outcome, words_required):
        submission = self.get_object()
        if not access.is_program_manager(request.user) and not access.leader_of(request.user):
            raise PermissionDenied("רק מוביל/ה מחליט/ה על הגשה.")

        said = (request.data.get("body") or "").strip()
        if words_required and not said:
            raise ValidationError(
                {
                    "body": "כדי להחזיר עבודה צריך לכתוב מה לשנות. "
                    "החזרה בלי מילים אומרת למי שכתב אותה שהוא נכשל, ולא מה לעשות."
                }
            )

        Feedback.objects.create(
            submission=submission, author=request.user, body=said, outcome=outcome
        )
        submission.status = outcome  # not-a-student-status: Submission
        submission.decided_by = request.user
        submission.decided_at = timezone.now()
        submission.save(update_fields=["status", "decided_by", "decided_at"])
        return Response(SubmissionSerializer(submission).data)

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        return self._decide(request, Submission.APPROVED, words_required=False)

    @action(detail=True, methods=["post"], url_path="send-back")
    def send_back(self, request, pk=None):
        return self._decide(request, Submission.RETURNED, words_required=True)


class FeedbackViewSet(NoUpdateMixin, NoDeleteMixin, Scoped):
    """REQ-M.123 — never edited, never deleted.

    The same reasoning as `StatusLog`, with one difference that makes it
    sharper: this one is read by a fourteen-year-old. Words that can be changed
    afterwards are words they cannot rely on having read.
    """

    serializer_class = FeedbackSerializer
    scope = staticmethod(access.visible_feedback)
    update_refusal = "מה שנכתב נשאר. אפשר להוסיף משוב חדש."
    delete_refusal = "משוב לא נמחק. מי שקרא אותו קרא אותו."

    def perform_create(self, serializer):
        submission = serializer.validated_data.get("submission")
        if not access.visible_submissions(self.request.user).filter(
            pk=getattr(submission, "pk", None)
        ).exists():
            raise NotFound()
        serializer.save(author=self.request.user, outcome=submission.status)


# --------------------------------------------- telling people, and the room


class NotificationViewSet(NoUpdateMixin, Scoped):
    """REQ-M.33 — your own bell.

    Creating one through the API is refused because it is forging somebody
    else's bell: a notification says "something happened to you", and a client
    that can write one can tell a teenager anything and point them anywhere.
    They are written by `notify.notify`, next to the thing that actually
    happened. Marking read and deleting your own are yours.
    """

    serializer_class = NotificationSerializer
    scope = staticmethod(access.visible_notifications)
    update_refusal = "התראה לא נערכת. אפשר לסמן כנקראה או למחוק."

    def create(self, request, *args, **kwargs):
        raise PermissionDenied("התראות נכתבות על ידי מה שקרה, לא על ידי בקשה.")

    @action(detail=True, methods=["post"], url_path="mark-read")
    def mark_read(self, request, pk=None):
        row = self.get_object()
        if row.read_at is None:
            row.read_at = timezone.now()
            row.save(update_fields=["read_at"])
        return Response(NotificationSerializer(row).data)


class EventViewSet(Scoped):
    """REQ-M.27 — ימי שיא. Owned by a program manager, aimed rather than broadcast."""

    serializer_class = EventSerializer
    scope = staticmethod(access.visible_events)

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return [IsSignedIn()]
        return [IsProgramManager()]

    def perform_create(self, serializer):
        data = serializer.validated_data
        if not data.get("for_everyone", True) and not (
            data.get("leaders") or data.get("classes")
        ):
            # An event for nobody is a row no screen can show.
            raise ValidationError(
                {"for_everyone": "בחרו למי האירוע: לכל התוכנית, או מובילים או כיתות."}
            )
        serializer.save(institution=access.institution_of(self.request.user))

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        """Taken down rather than deleted: somebody arranged their week around it."""
        event = self.get_object()
        if event.cancelled_at is None:
            event.cancelled_at = timezone.now()
            event.save(update_fields=["cancelled_at"])
        return Response(EventSerializer(event).data)


class PostViewSet(Scoped):
    """קהילת מט״צים (REQ-M.26, REQ-M.131, §4.12).

    Three departures from plain CRUD, each a requirement. `create` stamps the
    author and the institution server-side and moderates the text. `destroy` is
    the writer's own withdrawal, never a way to remove somebody else's words.
    And a take-down is not `destroy` at all but `hide`, because a post that
    vanishes teaches its writer nothing.
    """

    serializer_class = PostSerializer
    permission_classes = [IsInTheProgramme]
    scope = staticmethod(access.readable_posts)

    def get_queryset(self):
        return self.scope(self.request.user).select_related(
            "author", "author__profile", "submission"
        )

    def perform_create(self, serializer):
        from .community_views import moderate

        user = self.request.user
        body = (serializer.validated_data.get("body") or "").strip()
        if len(body) < 2:
            raise ValidationError({"body": "כדאי לכתוב משהו לפני ששולחים."})

        ok, why = moderate(body, user)
        if not ok:
            raise ValidationError({"body": why})

        submission = serializer.validated_data.get("submission")
        if submission is not None:
            owned = Submission.objects.filter(
                pk=submission.pk,
                student__user=user,
                status=Submission.APPROVED,
                shared_as__isnull=True,
            ).exists()
            if not owned:
                raise ValidationError({"submission": "התוצר הזה לא זמין לשיתוף."})

        serializer.save(
            author=user,
            institution=access.institution_of(user),
            kind=(
                Post.ANNOUNCEMENT
                if access.is_program_manager(user)
                else (Post.WORK if submission else Post.POST)
            ),
        )

    def perform_update(self, serializer):
        from .community_views import moderate

        if serializer.instance.author_id != self.request.user.id:
            raise PermissionDenied("אפשר לערוך רק את מה שכתבתם.")
        ok, why = moderate(
            (serializer.validated_data.get("body") or "").strip(), self.request.user
        )
        if not ok:
            raise ValidationError({"body": why})
        serializer.save()

    def perform_destroy(self, instance):
        if instance.author_id != self.request.user.id:
            raise PermissionDenied(
                "פוסט של מישהו אחר לא נמחק. אפשר להסתיר אותו, עם סיבה."
            )
        instance.delete()

    @action(detail=True, methods=["post"])
    def hide(self, request, pk=None):
        """REQ-M.131 — taken down by a person, with a reason, never deleted."""
        if not access.is_program_manager(request.user):
            raise PermissionDenied("רק מנהל/ת התוכנית יכולה להסתיר.")

        post = access.visible_posts(request.user).filter(pk=pk).first()
        if post is None:
            raise NotFound()

        reason = (request.data.get("reason") or "").strip()
        if not reason:
            raise ValidationError(
                {
                    "reason": "כדי להסתיר פוסט צריך לכתוב למה. "
                    "הסתרה בלי מילים לא אומרת לכותב כלום."
                }
            )

        post.hidden_at = timezone.now()
        post.hidden_by = request.user
        post.hidden_reason = reason
        post.save(update_fields=["hidden_at", "hidden_by", "hidden_reason"])
        return Response(PostSerializer(post).data)

    @action(detail=True, methods=["post"])
    def show(self, request, pk=None):
        """The way back. A judgement can be a mistake."""
        if not access.is_program_manager(request.user):
            raise PermissionDenied("רק מנהל/ת התוכנית יכולה להחזיר.")

        post = access.visible_posts(request.user).filter(pk=pk).first()
        if post is None:
            raise NotFound()

        post.hidden_at = None
        post.hidden_by = None
        post.hidden_reason = ""
        post.save(update_fields=["hidden_at", "hidden_by", "hidden_reason"])
        return Response(PostSerializer(post).data)


class TeachingSessionViewSet(Scoped):
    """REQ-M.32 — פרקטיקום, the stage the whole programme exists to produce.

    A member writes their own and nobody else's; their leader reads it because
    a leader who approves work and signs a certificate should be able to see
    the teaching being certified. Editing is real CRUD and deliberate: this is
    a teenager's own account of their own year, and getting the number of
    learners wrong should be fixable without asking anybody.

    `cancel` rather than a `cancelled_at` a client can set, so a session that
    did not happen is always something somebody marked.
    """

    serializer_class = TeachingSessionSerializer
    scope = staticmethod(access.visible_sessions)

    def perform_create(self, serializer):
        student = Student.objects.filter(user=self.request.user).first()
        if student is None:
            raise PermissionDenied("הפרקטיקום נפתח כשמצטרפים למוביל/ה.")
        serializer.save(student=student)

    def _mine_or_refuse(self, instance):
        if instance.student.user_id != self.request.user.id:
            raise PermissionDenied("זה התיעוד של מישהו אחר.")

    def perform_update(self, serializer):
        self._mine_or_refuse(serializer.instance)
        serializer.save()

    def perform_destroy(self, instance):
        self._mine_or_refuse(instance)
        instance.delete()

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        """It was planned and did not happen. The row stays and stops counting."""
        session = self.get_object()
        self._mine_or_refuse(session)
        if session.cancelled_at is None:
            session.cancelled_at = timezone.now()
            session.save(update_fields=["cancelled_at"])
        return Response(TeachingSessionSerializer(session).data)


# ------------------------------------------------------- the improvement loop


class RequestViewSet(NoDeleteMixin, Scoped):
    """§4.11 — what the person who runs the programme asked for.

    **Her words are hers** (REQ-M.112). The body is editable only by its author
    and only while it is still a draft, because once it is filed, Avi has read
    what she wrote and a later edit changes the thing he decided on. Everything
    else on the row is written beside her words and never over them: the
    assessment is machine-written and advisory, the decision is Avi's press.

    **The queue cannot start work.** `approve` marks a row ready and summons
    nobody. Nothing in this app triggers a sprint.
    """

    serializer_class = RequestSerializer
    scope = staticmethod(access.visible_requests)
    permission_classes = [IsProgramManager]
    delete_refusal = "בקשה לא נמחקת. אפשר לדחות אותה, וזה נשאר רשום."

    def perform_create(self, serializer):
        serializer.save(
            author=self.request.user,
            author_role=access.role_of(self.request.user),
            status=Request.NEW,
        )

    def perform_update(self, serializer):
        row = serializer.instance
        if row.author_id != self.request.user.id:
            raise PermissionDenied("המילים שלה הן שלה.")
        if row.status != Request.DRAFT:
            raise PermissionDenied("בקשה שנשלחה לא נערכת. מה שנכתב הוא מה שנקרא.")
        serializer.save()

    def _decide(self, request, status):
        if not request.user.is_superuser:
            raise PermissionDenied("ההחלטה היא של מנהל המוצר.")
        row = self.get_object()
        row.status = status  # not-a-student-status: Request
        row.decided_by = request.user
        row.decided_at = timezone.now()
        row.save(update_fields=["status", "decided_by", "decided_at"])
        return Response(RequestSerializer(row).data)

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        return self._decide(request, Request.APPROVED)

    @action(detail=True, methods=["post"])
    def decline(self, request, pk=None):
        return self._decide(request, Request.DECLINED)


class RequestMessageViewSet(NoUpdateMixin, NoDeleteMixin, Scoped):
    """REQ-M.115 — one turn of the conversation behind a request.

    A conversation is not rewritten after the fact. The chat may propose new
    wording and never replaces what she typed unless she takes the proposal.
    """

    serializer_class = RequestMessageSerializer
    scope = staticmethod(access.visible_request_messages)
    permission_classes = [IsProgramManager]
    update_refusal = "שיחה לא נערכת בדיעבד."
    delete_refusal = "שיחה לא נמחקת."

    def perform_create(self, serializer):
        parent = serializer.validated_data.get("request")
        if not access.visible_requests(self.request.user).filter(
            pk=getattr(parent, "pk", None)
        ).exists():
            raise NotFound()
        serializer.save(who=RequestMessage.HER)


# Every model in this app, and the route it answers on. Kept here rather than in
# urls.py so that adding a model and forgetting its endpoint is visible in one
# place: `test_every_model_has_an_endpoint` reads this.
ROUTES = [
    ("institutions", InstitutionViewSet, Institution),
    ("member-profiles", MemberProfileViewSet, MemberProfile),
    ("leaders", LeaderViewSet, Leader),
    ("classes", StudyClassViewSet, StudyClass),
    ("students", StudentViewSet, Student),
    ("entrance-targets", EntranceTargetViewSet, EntranceTarget),
    ("entrance-attempts", EntranceAttemptViewSet, EntranceAttempt),
    ("leader-invites", LeaderInviteViewSet, LeaderInvite),
    ("applications", ApplicationViewSet, Application),
    ("status-logs", StatusLogViewSet, StatusLog),
    ("certificates", MatazCertificateViewSet, MatazCertificate),
    ("retention-runs", RetentionRunViewSet, RetentionRun),
    ("submissions", SubmissionViewSet, Submission),
    ("feedback", FeedbackViewSet, Feedback),
    ("notifications", NotificationViewSet, Notification),
    ("events", EventViewSet, Event),
    ("posts", PostViewSet, Post),
    ("requests", RequestViewSet, Request),
    ("request-messages", RequestMessageViewSet, RequestMessage),
    ("teaching", TeachingSessionViewSet, TeachingSession),
]
