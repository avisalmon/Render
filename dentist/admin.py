"""Django admin for dentist's models.

Registered so the shapes can be inspected and demo data corrected in
development. Note what this is not: it is not a way for the site admin to
read patients. Rule 3.3 says the superuser sees nothing clinical, and the
admin is a superuser's tool, so the clinical models here are read-only
lists of ids and dates, and the one with names (Patient) shows only the
clinic number. Anything a person needs to do with a record happens in the
app, logged.
"""

from django.contrib import admin

from . import models


@admin.register(models.Clinic)
class ClinicAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "is_pilot", "created_at")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(models.ClinicMember)
class ClinicMemberAdmin(admin.ModelAdmin):
    list_display = ("clinic", "user", "role", "active")
    list_filter = ("clinic", "role", "active")


@admin.register(models.Invitation)
class InvitationAdmin(admin.ModelAdmin):
    list_display = ("clinic", "email", "role", "sent_at", "accepted_at")
    readonly_fields = ("token",)


@admin.register(models.Chair)
class ChairAdmin(admin.ModelAdmin):
    list_display = ("clinic", "name", "active", "order")


@admin.register(models.ProcedureType)
class ProcedureTypeAdmin(admin.ModelAdmin):
    list_display = ("clinic", "code", "name_en", "needs_consent", "active")
    list_filter = ("clinic",)


@admin.register(models.ReminderTemplate)
class ReminderTemplateAdmin(admin.ModelAdmin):
    list_display = ("clinic", "language", "kind")


class ClinicalReadOnly(admin.ModelAdmin):
    """Ids and dates only (Rule 3.3, 9.4). No add, no change, no delete."""

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(models.Patient)
class PatientAdmin(ClinicalReadOnly):
    list_display = ("clinic", "clinic_number", "status", "is_demo", "created_at")
    fields = ("clinic", "clinic_number", "status", "is_demo", "created_at")
    readonly_fields = fields
    search_fields = ("clinic_number",)


for model in (models.AccessLog, models.Visit, models.Appointment, models.Attachment, models.Consent):
    admin.site.register(model, ClinicalReadOnly)
