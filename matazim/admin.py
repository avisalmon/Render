"""מט״צים in Django's admin.

This is the escape hatch REQ-M.68 needs. Adminship is never self-served inside
מט״צים, because the first admin could never have used a screen that requires
being one. Two ways in, then: the `matazim_admins` command reading
`MATAZIM_ADMINS` on every deploy, and here, where only a site superuser can
reach it.

Django's admin is babook's plumbing and the spec lists it as shared. It is not a
מט״צים surface, no member ever sees it, and RULE-2 is about the templates under
templates/matazim/, so nothing is bent by being here.
"""

from django.contrib import admin

from .models import (
    EntranceAttempt,
    EntranceTarget,
    Institution,
    Leader,
    MemberProfile,
    Student,
    StudyClass,
)


@admin.register(Institution)
class InstitutionAdmin(admin.ModelAdmin):
    """Where the program-manager role is granted by hand.

    The role is `managers`, and this is the escape hatch for granting it to a
    named person without a deploy, which `MemberProfileAdmin` used to be when
    the role was a flag. Root only, like every Django admin screen here.
    """

    list_display = ("name", "manager_count", "created_at")
    filter_horizontal = ("managers",)
    search_fields = ("name", "managers__email")

    @admin.display(description="מנהלים/ות")
    def manager_count(self, obj):
        return obj.managers.count()


@admin.register(MemberProfile)
class MemberProfileAdmin(admin.ModelAdmin):
    """A person's מט״צים row. The program-manager role is not here any more:
    it is `Institution.managers`, granted on that screen."""

    list_display = (
        "email",
        "entered_via_matazim",
        "passed_test",
        "first_seen_at",
    )
    list_filter = ("entered_via_matazim",)
    search_fields = ("user__email", "user__username", "user__profile__display_name")
    readonly_fields = ("first_seen_at", "updated_at")
    autocomplete_fields = ("user",)

    @admin.display(description="אימייל", ordering="user__email")
    def email(self, obj):
        return obj.user.email or obj.user.username

    @admin.display(description="עבר מבחן כניסה", boolean=True)
    def passed_test(self, obj):
        return obj.has_passed_entrance_test()


class StudyClassInline(admin.TabularInline):
    model = StudyClass
    extra = 0
    fields = ("name", "school_name", "year", "is_active")


@admin.register(Leader)
class LeaderAdmin(admin.ModelAdmin):
    list_display = ("email", "is_active", "class_count", "student_count", "assigned_at")
    list_filter = ("is_active",)
    search_fields = ("user__email", "user__username", "contact")
    readonly_fields = ("join_code", "assigned_at")
    autocomplete_fields = ("user", "assigned_by")
    inlines = [StudyClassInline]

    @admin.display(description="אימייל", ordering="user__email")
    def email(self, obj):
        return obj.user.email or obj.user.username

    @admin.display(description="כיתות")
    def class_count(self, obj):
        return obj.classes.count()

    @admin.display(description="מט״צים")
    def student_count(self, obj):
        return obj.students.count()


@admin.register(StudyClass)
class StudyClassAdmin(admin.ModelAdmin):
    list_display = ("name", "school_name", "leader", "year", "is_active", "student_count")
    list_filter = ("school_name", "year", "is_active")
    search_fields = ("name", "school_name", "leader__user__email")

    @admin.display(description="מט״צים")
    def student_count(self, obj):
        return obj.students.count()


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ("email", "status", "leader", "cohort_year", "joined_at")
    # Someone with no leader is a normal state (REQ-M.65), and this filter is
    # how an admin finds the queue of people nobody has taken yet.
    list_filter = ("status", "cohort_year", "leader")
    search_fields = ("user__email", "user__username")
    autocomplete_fields = ("user", "leader")
    filter_horizontal = ("classes",)
    readonly_fields = ("joined_at", "updated_at")

    @admin.display(description="אימייל", ordering="user__email")
    def email(self, obj):
        return obj.user.email or obj.user.username


@admin.register(EntranceTarget)
class EntranceTargetAdmin(admin.ModelAdmin):
    list_display = ("target_id", "title", "shape", "is_retired", "retired_at")
    list_filter = ("shape", "is_retired")
    search_fields = ("target_id", "title")


@admin.register(EntranceAttempt)
class EntranceAttemptAdmin(admin.ModelAdmin):
    list_display = ("member", "number", "target_id", "passed", "submitted_at")
    list_filter = ("passed",)
    search_fields = ("member__user__email", "target_id")
    readonly_fields = ("measured", "issues", "created_at")
