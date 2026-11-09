"""The REST API under /gallery/api/ (Rule 6, REQ-G.103). Reading is open to
everybody, like the pages; writing needs a sign-in; a row that is not yours to
change is a refusal, never a quiet success."""

from django.utils import timezone
from rest_framework import mixins, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response

from . import access, shots, skillpack, skills
from . import skill_chat as chat_engine
from .models import AICall, Comment, Exhibit, Like, Person, Skill, SkillChat, Star, Strike, Topic, Training
from .serializers import (
    CommentSerializer, ExhibitSerializer, LikeSerializer, PersonAdminSerializer, PersonOwnSerializer,
    PersonPublicSerializer, StarSerializer, TopicSerializer, TrainingSerializer,
    AICallSerializer, SkillChatSerializer, SkillSerializer, StrikeSerializer,
)
from .views import search


class ReadOpenWriteSignedIn(permissions.BasePermission):
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        return bool(request.user and request.user.is_authenticated)


class SignedIn(permissions.BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)


class AdminWrites(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.method in permissions.SAFE_METHODS or access.is_admin(request.user)


def me(request):
    return access.ensure_person(request.user)


class PersonViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.UpdateModelMixin,
                    mixins.DestroyModelMixin, viewsets.GenericViewSet):
    """Public names for everybody; `persons/me/` for your own row (with your
    training); full rows for Avi. A row is created by acting, never here."""

    queryset = Person.objects.select_related("user", "training")
    permission_classes = [ReadOpenWriteSignedIn]
    lookup_field = "slug"
    lookup_value_regex = "[^/]+"

    def get_serializer_class(self):
        if access.is_admin(self.request.user):
            return PersonAdminSerializer
        return PersonPublicSerializer

    def perform_update(self, serializer):
        if not access.is_admin(self.request.user):
            raise PermissionDenied("only Avi changes another person; use persons/me/")
        serializer.save()

    def perform_destroy(self, instance):
        if not access.is_admin(self.request.user):
            raise PermissionDenied("only Avi removes a person")
        instance.delete()

    @action(detail=False, methods=["get", "patch"], permission_classes=[SignedIn])
    def me(self, request):
        person = me(request)
        if request.method == "GET":
            return Response(PersonOwnSerializer(person).data)
        serializer = PersonOwnSerializer(person, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        person = serializer.save()
        if {"training", "training_other"} & set(request.data) and not person.training_set_at:
            person.training_set_at = timezone.now()
            person.save(update_fields=["training_set_at"])
        return Response(PersonOwnSerializer(person).data)


class TrainingViewSet(viewsets.ModelViewSet):
    """The list is not secret (it is the question's choices); writes are Avi's."""

    serializer_class = TrainingSerializer
    permission_classes = [AdminWrites]

    def get_queryset(self):
        qs = Training.objects.all()
        return qs if access.is_admin(self.request.user) else qs.filter(is_open=True)


class TopicViewSet(viewsets.ModelViewSet):
    queryset = Topic.objects.all()
    serializer_class = TopicSerializer
    permission_classes = [AdminWrites]
    lookup_field = "slug"


class ExhibitViewSet(viewsets.ModelViewSet):
    """Cards. `?q=`, `?kind=`, `?topic=`, `?person=<slug>` search the same way
    the page does. Skills are created by the skill chat (SPR-G.6), not here."""

    serializer_class = ExhibitSerializer
    permission_classes = [ReadOpenWriteSignedIn]

    def get_queryset(self):
        p = self.request.query_params
        qs = search(Exhibit.objects.select_related("owner").prefetch_related("topics"),
                    (p.get("q") or "")[:200], p.get("kind", ""), p.get("topic", ""))
        if p.get("person"):
            qs = qs.filter(owner__slug=p["person"])
        return qs

    def _check(self, card):
        person = me(self.request)
        if card.owner_id != person.pk and not person.admin:
            raise PermissionDenied("not your card")

    def perform_create(self, serializer):
        person = me(self.request)
        if not person.answered_training:
            raise ValidationError({"training": "answer persons/me/ training first (REQ-G.4)"})
        kind = serializer.validated_data.get("kind", Exhibit.PAGE)
        if kind == Exhibit.SKILL:
            raise ValidationError({"kind": "skills come in through the skill chat"})
        if kind == Exhibit.BKM and not person.admin:
            raise PermissionDenied("BKM cards are Avi's")
        card = serializer.save(owner=person)
        shots.take(card)

    def perform_update(self, serializer):
        self._check(serializer.instance)
        kind = serializer.validated_data.get("kind")
        if kind and kind != serializer.instance.kind:
            if Exhibit.SKILL in (kind, serializer.instance.kind) or not me(self.request).admin:
                raise PermissionDenied("the kind of a card does not change")
        serializer.save()

    def perform_destroy(self, instance):
        self._check(instance)
        if instance.kind == Exhibit.SKILL and hasattr(instance, "skill"):
            skills.remove_files(instance.skill)
        if instance.shot:
            instance.shot.delete(save=False)
        instance.delete()

    @action(detail=True, methods=["post"])
    def retake(self, request, pk=None):
        card = self.get_object()
        self._check(card)
        card.shot_status, card.shot_tries = Exhibit.WAITING, 0
        card.save(update_fields=["shot_status", "shot_tries"])
        shots.take(card)
        return Response(ExhibitSerializer(card).data)

    def _toggle(self, request, model):
        card = self.get_object()
        person = me(request)
        row = model.objects.filter(person=person, exhibit=card).first()
        if row:
            row.delete()
            on = False
        else:
            model.objects.get_or_create(person=person, exhibit=card)
            on = True
        body = {"on": on}
        if model is Like:
            body["count"] = card.likes.count()
        return Response(body)

    @action(detail=True, methods=["post"])
    def like(self, request, pk=None):
        return self._toggle(request, Like)

    @action(detail=True, methods=["post"])
    def star(self, request, pk=None):
        return self._toggle(request, Star)


class LikeViewSet(mixins.CreateModelMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin,
                  mixins.DestroyModelMixin, viewsets.GenericViewSet):
    """Likes are public. You add and remove your own."""

    serializer_class = LikeSerializer
    permission_classes = [ReadOpenWriteSignedIn]
    model = Like

    def get_queryset(self):
        qs = Like.objects.all()
        card = self.request.query_params.get("exhibit")
        return qs.filter(exhibit_id=card) if card else qs

    def perform_create(self, serializer):
        person = me(self.request)
        existing = self.model.objects.filter(person=person, exhibit=serializer.validated_data["exhibit"]).first()
        serializer.instance = existing or serializer.save(person=person)

    def perform_destroy(self, instance):
        if instance.person_id != me(self.request).pk:
            raise PermissionDenied("not yours")
        instance.delete()


class StarViewSet(LikeViewSet):
    """Stars are private: the queryset is your own, and nothing else exists."""

    serializer_class = StarSerializer
    permission_classes = [SignedIn]
    model = Star

    def get_queryset(self):
        return Star.objects.filter(person=me(self.request))


class CommentViewSet(viewsets.ModelViewSet):
    serializer_class = CommentSerializer
    permission_classes = [ReadOpenWriteSignedIn]

    def get_queryset(self):
        qs = Comment.objects.select_related("author")
        card = self.request.query_params.get("exhibit")
        return qs.filter(exhibit_id=card) if card else qs

    def perform_create(self, serializer):
        serializer.save(author=me(self.request))

    def perform_update(self, serializer):
        c = serializer.instance
        if c.author_id != me(self.request).pk:
            raise PermissionDenied("only your own comment")
        if c.deleted_at:
            raise PermissionDenied("deleted")
        serializer.save(edited_at=timezone.now())

    def perform_destroy(self, instance):
        person = me(self.request)
        if instance.author_id != person.pk and not person.admin:
            raise PermissionDenied("only your own comment")
        instance.deleted_at = timezone.now()
        instance.save(update_fields=["deleted_at"])



class SkillViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.DestroyModelMixin, viewsets.GenericViewSet):
    """Published skills, open to read (REQ-G.40). A skill is created and
    updated only through a skill chat (`skillchats`), never directly here;
    its owner or Avi deletes it."""

    serializer_class = SkillSerializer
    permission_classes = [ReadOpenWriteSignedIn]
    queryset = Skill.objects.select_related("exhibit__owner", "current").prefetch_related("current__files")

    def perform_destroy(self, instance):
        person = me(self.request)
        if instance.exhibit.owner_id != person.pk and not person.admin:
            raise PermissionDenied("not your skill")
        skills.remove_files(instance)
        instance.exhibit.delete()


class SkillChatViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.CreateModelMixin, viewsets.GenericViewSet):
    """The upload conversation (REQ-G.50 to G.56), the same rules as the page:
    POST a multipart `skill` file (and `update_of`, a skill id, for a new
    version) to start; POST `act/` with `action` (go_on, stop, fix with a
    `skill` file, publish, retry, reply with `reply`). Your own chats; Avi
    reads them all but speaks in none."""

    serializer_class = SkillChatSerializer
    permission_classes = [SignedIn]

    def get_queryset(self):
        qs = SkillChat.objects.prefetch_related("messages", "proposed_topics")
        return qs if access.is_admin(self.request.user) else qs.filter(person=me(self.request))

    def create(self, request, *args, **kwargs):
        person = me(request)
        if not person.answered_training:
            raise ValidationError({"training": "answer persons/me/ training first (REQ-G.4)"})
        skill = None
        if request.data.get("update_of"):
            skill = Skill.objects.filter(pk=request.data["update_of"]).select_related("exhibit").first()
            if skill is None or skill.exhibit.owner_id != person.pk:
                raise PermissionDenied("not your skill")
        allowed, why = skills.may_start(person, skill)
        if not allowed:
            raise PermissionDenied(why)
        upload = request.FILES.get("skill")
        if upload is None or upload.size > skillpack.MAX_UPLOAD:
            raise ValidationError({"skill": "skill.no_file" if upload is None else "skill.too_big"})
        try:
            chat, _bundle, _found = skills.start(person, upload.name, upload.read(), skill=skill)
        except skillpack.Refused as refused:
            raise ValidationError({"skill": refused.key, "detail": refused.detail}) from None
        chat_engine.begin(chat, getattr(request, "gallery_language", "he"))
        chat.refresh_from_db()
        return Response(SkillChatSerializer(chat).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def act(self, request, pk=None):
        chat = SkillChat.objects.filter(pk=pk, person=me(request)).first()
        if chat is None:
            raise PermissionDenied("only the uploader speaks in a chat")
        upload = None
        if request.data.get("action") == "fix":
            f = request.FILES.get("skill")
            if f is None or f.size > skillpack.MAX_UPLOAD:
                raise ValidationError({"skill": "skill.no_file" if f is None else "skill.too_big"})
            upload = (f.name, f.read())
        problem = chat_engine.act(chat, request.data.get("action", ""), getattr(request, "gallery_language", "he"),
                                  upload=upload, reply=str(request.data.get("reply", "")))
        chat.refresh_from_db()
        body = SkillChatSerializer(chat).data
        if problem:
            body["problem"] = problem
        return Response(body)


class AdminOnly(permissions.BasePermission):
    def has_permission(self, request, view):
        return access.is_admin(request.user)


class AICallViewSet(viewsets.ReadOnlyModelViewSet):
    """Every model call, for Avi (REQ-G.64). Written only by the chat."""

    serializer_class = AICallSerializer
    permission_classes = [AdminOnly]
    queryset = AICall.objects.all()


class StrikeViewSet(viewsets.ReadOnlyModelViewSet):
    """Risky uploads, for Avi (REQ-G.70). Cleared on his people screen."""

    serializer_class = StrikeSerializer
    permission_classes = [AdminOnly]
    queryset = Strike.objects.all()


ROUTES = [
    ("persons", PersonViewSet, Person),
    ("trainings", TrainingViewSet, Training),
    ("topics", TopicViewSet, Topic),
    ("exhibits", ExhibitViewSet, Exhibit),
    ("likes", LikeViewSet, Like),
    ("stars", StarViewSet, Star),
    ("comments", CommentViewSet, Comment),
    ("skills", SkillViewSet, Skill),
    ("skillchats", SkillChatViewSet, SkillChat),
    ("aicalls", AICallViewSet, AICall),
    ("strikes", StrikeViewSet, Strike),
]
