from django.contrib import admin

from .models import (
    AuthoringJob,
    ChatMessage,
    ChatSession,
    CopilotSeat,
    CorporateLead,
    Course,
    CourseCertificate,
    CourseMaterial,
    Enrollment,
    Entitlement,
    LearnerProfile,
    LessonQuiz,
    LessonReflection,
    ModerationLog,
    NewsletterSubscriber,
    Note,
    SeatEvent,
    SystemPrompt,
    UsageLog,
    UserProfile,
    UserVideoProgress,
    Video,
)

admin.site.register(Note)
admin.site.register(UserProfile)


@admin.register(LearnerProfile)
class LearnerProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "experience_level", "recommended_track",
                    "onboarding_completed_at", "source_entry_type", "created_at")
    search_fields = ("user__username", "goal", "source_course")
    list_filter = ("experience_level", "source_entry_type")


class CourseMaterialInline(admin.TabularInline):
    model = CourseMaterial
    extra = 1
    fields = ("order", "title", "material_type", "url", "file")


class CourseWithMaterialsAdmin(admin.ModelAdmin):
    inlines = [CourseMaterialInline]


admin.site.register(Course, CourseWithMaterialsAdmin)
admin.site.register(CourseMaterial)
admin.site.register(Video)
admin.site.register(UserVideoProgress)
admin.site.register(Enrollment)
admin.site.register(Entitlement)
admin.site.register(CopilotSeat)
admin.site.register(SeatEvent)
admin.site.register(SystemPrompt)
admin.site.register(ChatSession)
admin.site.register(ChatMessage)
admin.site.register(UsageLog)
admin.site.register(ModerationLog)
admin.site.register(CorporateLead)
admin.site.register(NewsletterSubscriber)
admin.site.register(LessonQuiz)
admin.site.register(CourseCertificate)


@admin.register(AuthoringJob)
class AuthoringJobAdmin(admin.ModelAdmin):
    list_display = ("id", "title", "source_type", "status", "progress", "course", "created_at")
    list_filter = ("status", "source_type")
    readonly_fields = ("created_at", "updated_at")


@admin.register(LessonReflection)
class LessonReflectionAdmin(admin.ModelAdmin):
    """Admin-only view of learner reflections (not shown on the user's own profile)."""
    list_display = ("user", "video", "short_text", "created_at")
    list_filter = ("created_at", "video__course")
    search_fields = ("user__username", "user_text", "ai_reply")
    readonly_fields = ("user", "video", "prompt", "user_text", "ai_reply", "created_at")
    date_hierarchy = "created_at"

    @admin.display(description="reflection")
    def short_text(self, obj):
        return (obj.user_text or "")[:80]
