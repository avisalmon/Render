from django.contrib import admin

from .models import (
    ChatMessage,
    ChatSession,
    CopilotSeat,
    CorporateLead,
    Course,
    CourseCertificate,
    CourseMaterial,
    Enrollment,
    Entitlement,
    LessonQuiz,
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
