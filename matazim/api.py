"""The REST API for קהילת מט״צים (REQ-M.134, methodology Rule 6).

**The queryset is `access.visible_posts`, and that is the whole point.** §4.4
says scope is a property of the data rather than a rule anyone remembers, and
an API that re-derived its own scope would be a second answer to the same
question, free to drift from the one the screens use. This viewset asks the
same function `community.html` asks.

This is the first מט״צים module with an API. The rest of the app predates Rule 6
and has none, which is recorded in spec §4.12 as a gap rather than an oversight.
"""

from rest_framework import permissions, serializers, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from django.utils import timezone

from .access import institution_of, is_program_manager, readable_posts, visible_posts
from .community_views import moderate
from .models import Post
from .serializers import PostSerializer


class IsInTheProgramme(permissions.BasePermission):
    """Signed in, and belonging to an institution.

    A candidate is signed in and belongs to nobody yet (REQ-M.99), so they get
    the same answer here as they get on the screen: not yours yet.
    """

    message = "הקהילה נפתחת כשמצטרפים לתוכנית."

    def has_permission(self, request, view):
        if not getattr(request.user, "is_authenticated", False):
            return False
        return institution_of(request.user) is not None


class PostViewSet(viewsets.ModelViewSet):
    """Full CRUD over the community's rows, inside one institution.

    Three departures from plain CRUD, each of them a requirement:

    `create` stamps the author and the institution server-side and moderates
    the text (REQ-M.131). `destroy` is the writer's own withdrawal only, never
    a way to remove somebody else's words. And a take-down is not `destroy` at
    all but the `hide` action, because REQ-M.131 says a moderated post keeps its
    row: a post that vanishes teaches its writer nothing.
    """

    serializer_class = PostSerializer
    permission_classes = [IsInTheProgramme]

    def get_queryset(self):
        return readable_posts(self.request.user).select_related(
            "author", "author__profile", "submission"
        )

    def perform_create(self, serializer):
        user = self.request.user
        body = (serializer.validated_data.get("body") or "").strip()
        if len(body) < 2:
            raise ValidationError({"body": "כדאי לכתוב משהו לפני ששולחים."})

        ok, why = moderate(body, user)
        if not ok:
            raise ValidationError({"body": why})

        submission = serializer.validated_data.get("submission")
        if submission is not None:
            # REQ-M.132: your own work, approved, and not already in the feed.
            from .models import Submission

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
            program_manager=institution_of(user),
            kind=(
                Post.ANNOUNCEMENT
                if is_program_manager(user)
                else (Post.WORK if submission else Post.POST)
            ),
        )

    def perform_update(self, serializer):
        if serializer.instance.author_id != self.request.user.id:
            raise PermissionDenied("אפשר לערוך רק את מה שכתבתם.")
        body = (serializer.validated_data.get("body") or "").strip()
        ok, why = moderate(body, self.request.user)
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
        if not is_program_manager(request.user):
            raise PermissionDenied("רק מנהל/ת התוכנית יכולה להסתיר.")

        post = visible_posts(request.user).filter(pk=pk).first()
        if post is None:
            raise PermissionDenied("לא נמצא.")

        reason = (request.data.get("reason") or "").strip()
        if not reason:
            raise ValidationError(
                {"reason": "כדי להסתיר פוסט צריך לכתוב למה. הסתרה בלי מילים לא אומרת לכותב כלום."}
            )

        post.hidden_at = timezone.now()
        post.hidden_by = request.user
        post.hidden_reason = reason
        post.save(update_fields=["hidden_at", "hidden_by", "hidden_reason"])
        return Response(PostSerializer(post).data)

    @action(detail=True, methods=["post"])
    def show(self, request, pk=None):
        """The way back from `hide`.

        A take-down is a person's judgement, so it can be a person's mistake,
        and `docs/building_an_app.md` asks whether a mistake can be fixed
        without going to /admin/. Not a `hide` with a flag, because a caller
        that forgets the flag should not accidentally publish something.
        """
        if not is_program_manager(request.user):
            raise PermissionDenied("רק מנהל/ת התוכנית יכולה להחזיר.")

        post = visible_posts(request.user).filter(pk=pk).first()
        if post is None:
            raise PermissionDenied("לא נמצא.")

        post.hidden_at = None
        post.hidden_by = None
        post.hidden_reason = ""
        post.save(update_fields=["hidden_at", "hidden_by", "hidden_reason"])
        return Response(PostSerializer(post).data)
