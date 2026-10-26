"""dentist's REST API (spec Rule 2.6; building_an_app.md Rule 6).

Every route lives under `/dentist/api/c/<clinic>/`, and one permission
class answers every request: is this signed-in person an active member of
that clinic, and, where the screen is the administrator's, an
administrator. Default deny: a patient's account, a superuser, a member of
another clinic get 403 before any queryset is built. The querysets come
from `access.py`, the same scope the screens use, so the two cannot drift.

D.3 covers the models the screens of D.2 and D.3 use; D.4 to D.6 add
theirs the day their screens arrive, and D.8 completes the set.
"""

from django.shortcuts import get_object_or_404
from rest_framework import mixins, permissions, serializers, viewsets
from rest_framework.exceptions import PermissionDenied
from rest_framework.routers import DefaultRouter

from . import access, people
from .models import AccessLog, Chair, Clinic, ClinicMember, HistoryItem, Invitation, Patient


class IsClinicMember(permissions.BasePermission):
    """Member of the clinic in the URL; administrator where the viewset says so."""

    message = "Not a member of this clinic."

    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        clinic = view.clinic()
        member = access.membership(request.user, clinic)
        if member is None:
            return False
        if getattr(view, "admin_only", False) and member.role != ClinicMember.ADMIN:
            self.message = "Administrators only."
            return False
        view.member = member
        return True


class ClinicScoped(viewsets.GenericViewSet):
    permission_classes = [IsClinicMember]
    admin_only = False

    def clinic(self):
        if not hasattr(self, "_clinic"):
            self._clinic = get_object_or_404(Clinic, slug=self.kwargs["slug"])
        return self._clinic


# --------------------------------------------------------------- patients


class PatientSerializer(serializers.ModelSerializer):
    class Meta:
        model = Patient
        exclude = ["user", "is_demo"]
        read_only_fields = ["clinic", "clinic_number", "created_by", "created_at", "updated_at"]


class PatientViewSet(ClinicScoped, viewsets.ModelViewSet):
    serializer_class = PatientSerializer

    def get_queryset(self):
        return access.patients_for(self.request.user, self.clinic())

    def perform_create(self, serializer):
        patient = serializer.save(clinic=self.clinic(), created_by=self.request.user)
        access.log(self.clinic(), self.request.user, "edited", patient=patient, what="api: patient created")

    def perform_update(self, serializer):
        patient = serializer.save()
        access.log(self.clinic(), self.request.user, "edited", patient=patient, what="api: patient details")

    def retrieve(self, request, *args, **kwargs):
        response = super().retrieve(request, *args, **kwargs)
        access.log(self.clinic(), request.user, "viewed", patient=self.get_object(), what="api: patient record")
        return response

    def perform_destroy(self, instance):
        from . import records

        if self.member.role != ClinicMember.ADMIN:
            raise PermissionDenied("Administrators only.")
        records.delete(instance, self.request.user)


class HistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = HistoryItem
        fields = ["id", "patient", "kind", "what", "detail", "alert", "active", "noted_by", "noted_at"]
        read_only_fields = ["noted_by", "noted_at"]

    def validate_patient(self, patient):
        view = self.context["view"]
        if patient.clinic_id != view.clinic().pk:
            raise serializers.ValidationError("Not a patient of this clinic.")
        return patient


class HistoryViewSet(ClinicScoped, viewsets.ModelViewSet):
    serializer_class = HistorySerializer

    def get_queryset(self):
        rows = HistoryItem.objects.filter(patient__in=access.patients_for(self.request.user, self.clinic()))
        patient = self.request.query_params.get("patient")
        return rows.filter(patient_id=patient) if patient else rows

    def perform_create(self, serializer):
        item = serializer.save(noted_by=self.request.user)
        access.log(self.clinic(), self.request.user, "edited", patient=item.patient, what="api: history added")

    def perform_destroy(self, instance):
        # Rule 4.4: a resolved item is kept, inactive, never deleted.
        instance.active = False
        instance.save(update_fields=["active"])


# ---------------------------------------------------------- the clinic's own


class MemberSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(source="user.email", read_only=True)

    class Meta:
        model = ClinicMember
        fields = ["id", "email", "role", "display_name", "active", "created_at"]
        read_only_fields = ["role", "created_at"]


class MemberViewSet(ClinicScoped, mixins.ListModelMixin, mixins.RetrieveModelMixin,
                    mixins.UpdateModelMixin, viewsets.GenericViewSet):
    """Members are made by invitation only (Rule 3.2): no create here, and
    no delete; `active` is the switch."""

    serializer_class = MemberSerializer
    admin_only = True

    def get_queryset(self):
        return self.clinic().members.select_related("user")


class InvitationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Invitation
        fields = ["id", "email", "role", "sent_at", "accepted_at"]
        read_only_fields = ["sent_at", "accepted_at"]


class InvitationViewSet(ClinicScoped, mixins.ListModelMixin, mixins.RetrieveModelMixin,
                        mixins.CreateModelMixin, mixins.DestroyModelMixin, viewsets.GenericViewSet):
    serializer_class = InvitationSerializer
    admin_only = True

    def get_queryset(self):
        return self.clinic().invitations.all()

    def perform_create(self, serializer):
        # Through the same door as the screen, so the mail is never forgotten.
        data = serializer.validated_data
        invitation, sent = people.invite(self.clinic(), data["email"], data["role"], self.request.user, self.request)
        serializer.instance = invitation
        self.sent = sent

    def perform_destroy(self, instance):
        if instance.accepted_at is not None:
            raise PermissionDenied("Accepted invitations are history, not deletable.")
        instance.delete()


class ChairSerializer(serializers.ModelSerializer):
    class Meta:
        model = Chair
        fields = ["id", "name", "active", "order"]


class ChairViewSet(ClinicScoped, viewsets.ModelViewSet):
    serializer_class = ChairSerializer
    admin_only = True

    def get_queryset(self):
        return self.clinic().chairs.all()

    def perform_create(self, serializer):
        serializer.save(clinic=self.clinic())


class AccessLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = AccessLog
        fields = ["id", "patient", "user", "action", "what", "at"]


class AccessLogViewSet(ClinicScoped, mixins.ListModelMixin, viewsets.GenericViewSet):
    """Read-only, administrators (Rule 4.5). A log that can be edited is
    not a log."""

    serializer_class = AccessLogSerializer
    admin_only = True

    def get_queryset(self):
        return self.clinic().access_log.all()[:500]


router = DefaultRouter()
for prefix, viewset in (("patients", PatientViewSet), ("history", HistoryViewSet), ("members", MemberViewSet),
                        ("invitations", InvitationViewSet), ("chairs", ChairViewSet), ("access-log", AccessLogViewSet)):
    router.register(prefix, viewset, basename=f"api-{prefix}")
