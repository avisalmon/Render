"""DRF serializers for every מט״צים model (REQ-M.139, methodology Rule 6).

One rule runs through this whole file, and it is the reason to read the top
before changing anything below.

**Anything that decides who a row belongs to is read-only and set on the server
from `request.user`.** Authors, institutions, join codes, invite tokens, public
ids, and the timestamps recording who decided what. A client that could name its
own author could post as another teenager. A client that could name its own
`program_manager` could write into another institution's world, which is §4.4
undone through the back door while every screen still looks correct.

**A second rule, narrower but just as load-bearing: `Student.status` is never
writable.** It changes through `matazim.history.set_status`, which writes the
`StatusLog` row in the same breath (§4.7). A serializer that accepted a status
would be a way to move a teenager between stages with no record of who did it,
and the sprm18 guard cannot see inside a `ModelSerializer`: it reads source for
bare assignments, and a serializer field is not one.

(That guard reads this file too, and an earlier draft of this paragraph tripped
it by quoting the pattern it greps for. Worth knowing before rewording it.)

Names, not emails, wherever a person is shown (§4.10). `PersonSerializer` is the
one shape used everywhere for that.
"""

from rest_framework import serializers

from .models import (
    Application,
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
)


class PersonSerializer(serializers.Serializer):
    """Just enough about a `User` to show who somebody is.

    The display name and never the email. An email is an identifier and a way
    to reach a child outside this product, and no screen here has ever needed
    one to say who did something.
    """

    id = serializers.IntegerField(read_only=True)
    name = serializers.SerializerMethodField()

    def get_name(self, user):
        if user is None:
            return ""
        profile = getattr(user, "profile", None)
        return (getattr(profile, "display_name", "") or "").strip() or "חבר/ת התוכנית"


# --- People and roles -------------------------------------------------------


class MemberProfileSerializer(serializers.ModelSerializer):
    user = PersonSerializer(read_only=True)

    class Meta:
        model = MemberProfile
        fields = [
            "id", "user", "birth_year", "guardian_name", "guardian_email",
            "guardian_consent_at", "entrance_test_passed_at", "is_program_manager",
            "entered_via_matazim", "welcome_accepted_at", "first_seen_at", "updated_at",
        ]
        # `is_program_manager` is read-only here and granted only through
        # `roles.grant_program_manager`, behind a root-only screen (REQ-M.114).
        # It was once settable by anyone holding the role, and the role could
        # therefore replicate itself across institutions.
        #
        # `entrance_test_passed_at` is read-only because passing is something
        # the test decides (REQ-M.36); a writable field here is a way to walk
        # through the gate to the whole programme.
        read_only_fields = [
            "id", "user", "is_program_manager", "entrance_test_passed_at",
            "entered_via_matazim", "welcome_accepted_at", "first_seen_at", "updated_at",
        ]


class LeaderSerializer(serializers.ModelSerializer):
    user = PersonSerializer(read_only=True)
    schools = serializers.SerializerMethodField()
    # Write-only, and an id rather than an email, because a leader is made out
    # of an account that already exists. `staff_admins` learned the same lesson
    # from the other side: a typo must never conjure an account holding a role.
    user_id = serializers.IntegerField(write_only=True, required=False)

    class Meta:
        model = Leader
        fields = [
            "id", "user", "user_id", "contact", "is_active", "approved_at",
            "approved_by", "program_manager", "assigned_at", "schools",
        ]
        # `join_code` is absent from `fields` entirely rather than read-only: a
        # code attaches its holder to this leader with no confirmation
        # (REQ-M.9), so a list endpoint that returned every leader's code would
        # be a harvest. It is shown by the leader's own screen, to them.
        #
        # `program_manager` is the tenancy root and is stamped server-side.
        read_only_fields = [
            "id", "user", "approved_at", "approved_by", "program_manager", "assigned_at",
        ]

    def get_schools(self, leader):
        return leader.school_names


class StudyClassSerializer(serializers.ModelSerializer):
    class Meta:
        model = StudyClass
        fields = ["id", "leader", "name", "school_name", "year", "is_active", "created_at"]
        read_only_fields = ["id", "created_at"]


class StudentSerializer(serializers.ModelSerializer):
    user = PersonSerializer(read_only=True)

    class Meta:
        model = Student
        fields = [
            "id", "user", "leader", "pending_leader", "status", "cohort_year",
            "certified_at", "certified_by", "joined_at", "updated_at", "classes",
        ]
        # `status` read-only: see the note at the top of this file. Moving
        # somebody between stages happens through `history.set_status` and the
        # viewset's `set_status` action, which writes the log.
        read_only_fields = [
            "id", "user", "status", "certified_at", "certified_by", "joined_at",
            "updated_at",
        ]


# --- The entrance test ------------------------------------------------------


class EntranceTargetSerializer(serializers.ModelSerializer):
    class Meta:
        model = EntranceTarget
        fields = [
            "id", "target_id", "shape", "title", "brief", "is_retired",
            "retired_by", "retired_at",
        ]
        read_only_fields = ["id", "retired_by", "retired_at"]


class EntranceAttemptSerializer(serializers.ModelSerializer):
    class Meta:
        model = EntranceAttempt
        fields = [
            "id", "member", "target_id", "number", "measured", "issues",
            "passed", "submitted_at", "created_at",
        ]
        # `model_file` is deliberately not a field. It is a minor's own work,
        # stored outside MEDIA_ROOT under a random name, and the only thing that
        # hands one over is a view that asks who is looking (REQ-M.80).
        read_only_fields = fields


# --- Joining ----------------------------------------------------------------


class LeaderInviteSerializer(serializers.ModelSerializer):
    class Meta:
        model = LeaderInvite
        fields = [
            "id", "program_manager", "kind", "label", "email", "used_at",
            "used_by", "revoked_at", "sent_at", "created_at",
        ]
        # `token` is absent for the same reason `join_code` is: it is the key.
        read_only_fields = [
            "id", "program_manager", "used_at", "used_by", "sent_at", "created_at",
        ]


class ApplicationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Application
        fields = ["id", "student", "asked", "grade", "motivation", "built_before", "created_at"]
        read_only_fields = ["id", "student", "created_at"]


# --- The record of decisions ------------------------------------------------


class StatusLogSerializer(serializers.ModelSerializer):
    changed_by = PersonSerializer(read_only=True)

    class Meta:
        model = StatusLog
        fields = [
            "id", "student", "from_status", "to_status", "changed_by",
            "from_leader", "to_leader", "note", "at",
        ]
        read_only_fields = fields  # append-only (§4.7)


class MatazCertificateSerializer(serializers.ModelSerializer):
    class Meta:
        model = MatazCertificate
        fields = [
            "id", "student", "public_id", "name_on_certificate",
            "awarded_by_name", "awarded_at", "revoked_at", "created_at",
        ]
        # The name and the awarding name are copies taken at issue time, not
        # joins: a certificate is a document about a moment and must not change
        # because somebody edited their display name two years later.
        read_only_fields = fields


class RetentionRunSerializer(serializers.ModelSerializer):
    ran_by = PersonSerializer(read_only=True)

    class Meta:
        model = RetentionRun
        fields = ["id", "ran_at", "ran_by", "deleted_count", "kind"]
        read_only_fields = fields


# --- The work, and the feedback that is the point ---------------------------


class SubmissionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Submission
        fields = [
            "id", "student", "leader", "title", "about", "link", "status",
            "answers", "decided_by", "decided_at", "created_at",
        ]
        # `work_file` absent for the same reason as `model_file` (REQ-M.122).
        # `status` read-only: it changes through the leader deciding, which is
        # the `approve` and `send_back` actions, because REQ-M.124 says sending
        # work back without words is refused and a bare field write has no
        # words in it.
        read_only_fields = [
            "id", "student", "status", "decided_by", "decided_at", "created_at",
        ]


class FeedbackSerializer(serializers.ModelSerializer):
    author = PersonSerializer(read_only=True)

    class Meta:
        model = Feedback
        fields = ["id", "submission", "author", "body", "outcome", "created_at"]
        read_only_fields = ["id", "author", "outcome", "created_at"]


# --- Telling people, and the room they are in -------------------------------


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ["id", "kind", "text", "url", "created_at", "read_at"]
        # `user` is absent: this endpoint only ever returns your own, so a field
        # naming the owner would be either redundant or a lie waiting to happen.
        read_only_fields = ["id", "kind", "text", "url", "created_at"]


class EventSerializer(serializers.ModelSerializer):
    class Meta:
        model = Event
        fields = [
            "id", "program_manager", "title", "about", "starts_at", "ends_at",
            "place", "for_everyone", "is_public", "cancelled_at", "created_at",
            "leaders", "classes",
        ]
        # `cancelled_at` read-only: cancelling tells everybody who was invited,
        # so it is the `cancel` action and not a date somebody can set quietly.
        read_only_fields = ["id", "program_manager", "cancelled_at", "created_at"]


class PostAuthorSerializer(PersonSerializer):
    """Kept as its own name because the community shipped with it."""


class PostSerializer(serializers.ModelSerializer):
    author = PostAuthorSerializer(read_only=True)
    kind_display = serializers.CharField(source="get_kind_display", read_only=True)
    is_hidden = serializers.BooleanField(read_only=True)
    submission_title = serializers.CharField(
        source="submission.title", read_only=True, default=""
    )

    class Meta:
        model = Post
        fields = [
            "id", "author", "kind", "kind_display", "body", "submission",
            "submission_title", "is_hidden", "hidden_reason", "created_at",
        ]
        read_only_fields = [
            "id", "author", "kind", "kind_display", "is_hidden",
            "hidden_reason", "created_at",
        ]


# --- The improvement loop ---------------------------------------------------


class RequestSerializer(serializers.ModelSerializer):
    author = PersonSerializer(read_only=True)

    class Meta:
        model = Request
        fields = [
            "id", "author", "author_role", "body", "kind", "from_screen",
            "status", "decided_by", "decided_at", "assessment", "assessed_at",
            "recommendation", "sprint", "outcome", "done_at", "created_at",
        ]
        # Everything except her own words and the kind is read-only. §4.11: the
        # assessment is advisory and machine-written, the decision is Avi's
        # press, and the log is the customer voice rather than a second plan.
        read_only_fields = [
            "id", "author", "author_role", "from_screen", "status", "decided_by",
            "decided_at", "assessment", "assessed_at", "recommendation", "sprint",
            "outcome", "done_at", "created_at",
        ]


class RequestMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = RequestMessage
        fields = ["id", "request", "who", "body", "created_at"]
        read_only_fields = ["id", "who", "created_at"]
