from django.contrib import admin

from .models import (
    AIGraderConfig,
    AuthoringJob,
    BadgeAward,
    BlogComment,
    BlogImage,
    BlogPost,
    BlogRead,
    ChatMessage,
    ChatSession,
    CommunityReputation,
    ContentReport,
    CopilotSeat,
    CorporateLead,
    Course,
    CourseCertificate,
    CourseMaterial,
    CourseProjectSubmission,
    DirectMessage,
    Enrollment,
    Entitlement,
    ForumPost,
    ForumThread,
    LearnerProfile,
    LessonModelSubmission,
    LessonQuiz,
    LessonReflection,
    ModerationLog,
    NewsletterSubscriber,
    Note,
    ProjectComment,
    SeatEvent,
    ShowcaseProject,
    SystemPrompt,
    UsageLog,
    UserProfile,
    UserVideoProgress,
    Video,
)

admin.site.register(Note)
admin.site.register(UserProfile)


# --- Community (EPIC-6.1/6.2) ---

@admin.register(ContentReport)
class ContentReportAdmin(admin.ModelAdmin):
    """The moderation queue (REQ-6.1.8)."""
    list_display = ("created_at", "content_type", "object_id", "reason",
                    "reporter", "status", "handled_by")
    list_filter = ("status", "content_type")
    actions = ["hide_reported_content", "dismiss_reports"]

    @admin.action(description="Hide reported content + mark actioned")
    def hide_reported_content(self, request, queryset):
        from django.utils import timezone
        for report in queryset:
            model = {
                "thread": ForumThread, "post": ForumPost,
                "project": ShowcaseProject, "projectcomment": ProjectComment,
            }.get(report.content_type)
            if model:
                model.objects.filter(pk=report.object_id).update(is_hidden=True)
            report.status = "actioned"
            report.handled_by = request.user
            report.handled_at = timezone.now()
            report.action_note = "content hidden"
            report.save()

    @admin.action(description="Dismiss reports")
    def dismiss_reports(self, request, queryset):
        from django.utils import timezone
        queryset.update(status="dismissed", handled_by=request.user,
                        handled_at=timezone.now())


@admin.register(ForumThread)
class ForumThreadAdmin(admin.ModelAdmin):
    list_display = ("title", "category", "kind", "author", "is_pinned",
                    "is_canonical", "is_hidden", "created_at")
    list_filter = ("category", "kind", "is_pinned", "is_canonical", "is_hidden")
    search_fields = ("title", "body", "author__username")


admin.site.register(ForumPost)
admin.site.register(BadgeAward)
admin.site.register(CommunityReputation)


@admin.register(ShowcaseProject)
class ShowcaseProjectAdmin(admin.ModelAdmin):
    """Showcase moderation + the student-work review queue (REQ-6.3.7)."""
    list_display = ("title", "author", "stand", "status", "is_featured",
                    "star_count", "is_hidden", "published_at")
    list_filter = ("status", "stand", "is_featured", "is_hidden")
    search_fields = ("title", "tagline", "author__username")
    actions = ["approve_projects", "feature_projects"]

    @admin.action(description="Approve (publish) selected projects")
    def approve_projects(self, request, queryset):
        from django.utils import timezone
        for p in queryset.filter(status="pending"):
            p.status = "published"
            if not p.published_at:
                p.published_at = timezone.now()
            p.save()

    @admin.action(description="Toggle featured (נבחרת השבוע)")
    def feature_projects(self, request, queryset):
        for p in queryset:
            p.is_featured = not p.is_featured
            p.save(update_fields=["is_featured"])


admin.site.register(ProjectComment)
admin.site.register(DirectMessage)


# --- Avi Salmon Blog (personal blog) ---

class BlogImageInline(admin.TabularInline):
    model = BlogImage
    extra = 1
    fields = ("image", "key", "alt", "caption", "order")


@admin.register(BlogPost)
class BlogPostAdmin(admin.ModelAdmin):
    """Author + publish the personal blog. Body is markdown (text, links,
    images, ```python-run runnable cells, and raw-HTML embeds)."""
    list_display = ("title", "status", "is_featured", "feature_order", "published_at", "view_count")
    list_filter = ("status", "is_featured")
    list_editable = ("is_featured", "feature_order")
    search_fields = ("title", "subtitle", "excerpt", "body")
    prepopulated_fields = {"slug": ("title",)}
    readonly_fields = ("view_count", "created_at", "updated_at")
    inlines = [BlogImageInline]
    actions = ["publish_posts"]
    fieldsets = (
        (None, {"fields": ("title", "subtitle", "slug", "author")}),
        ("Card & SEO", {"fields": ("cover", "excerpt", "tags")}),
        ("Content", {"fields": ("body",)}),
        # is_featured = show full-width on the index; feature_order = its position
        # among the full-width posts (1, 2, 3 ...).
        ("Publishing", {"fields": ("status", "is_featured", "feature_order", "published_at")}),
        ("Meta", {"fields": ("view_count", "created_at", "updated_at")}),
    )

    @admin.action(description="Publish selected posts")
    def publish_posts(self, request, queryset):
        from django.utils import timezone
        for p in queryset.exclude(status="published"):
            p.status = "published"
            if not p.published_at:
                p.published_at = timezone.now()
            p.save()


@admin.register(BlogComment)
class BlogCommentAdmin(admin.ModelAdmin):
    """Readers' private messages to Avi about a post (also emailed)."""
    list_display = ("created_at", "post", "name", "email", "emailed")
    list_filter = ("emailed",)
    search_fields = ("name", "email", "body", "post__title")
    readonly_fields = ("post", "user", "name", "email", "body", "emailed", "created_at")


admin.site.register(BlogRead)


@admin.register(LearnerProfile)
class LearnerProfileAdmin(admin.ModelAdmin):
    """The admin's full view of everything onboarding captured (REQ-5.6.1)."""
    list_display = ("user", "display_name", "role_type", "experience_level",
                    "recommended_track", "goal", "interests",
                    "onboarding_completed_at", "source_entry_type", "created_at")
    search_fields = ("user__username", "user__email", "goal", "persona", "source_course")
    list_filter = ("role_type", "experience_level", "recommended_track", "source_entry_type")
    readonly_fields = ("created_at",)

    @admin.display(description="Name")
    def display_name(self, obj):
        return obj.user.profile.display_name or obj.user.first_name


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
@admin.register(CourseProjectSubmission)
class CourseProjectSubmissionAdmin(admin.ModelAdmin):
    """Proof-of-work submissions + the AI correctness verdict (advisory)."""
    list_display = ("user", "course", "grade_ok", "grade_score", "graded_model",
                    "short_reason", "created_at")
    list_filter = ("grade_ok", "graded_model", "course")
    search_fields = ("user__username", "course__slug", "grade_reason")
    readonly_fields = ("grade_ok", "grade_score", "grade_reason", "graded_model",
                       "graded_hash", "graded_at")

    @admin.display(description="AI reason")
    def short_reason(self, obj):
        return (obj.grade_reason or "")[:80]


admin.site.register(LessonModelSubmission)


from .models import StudentCode  # noqa: E402


@admin.register(StudentCode)
class StudentCodeAdmin(admin.ModelAdmin):
    """Admin view of learners' in-lesson practice code (runs in-browser)."""
    list_display = ("user", "video", "cell_key", "passed", "updated_at")
    list_filter = ("passed", "updated_at", "video__course")
    search_fields = ("user__username", "code", "cell_key")
    readonly_fields = ("user", "video", "cell_key", "code", "passed", "updated_at")
    date_hierarchy = "updated_at"


@admin.register(AIGraderConfig)
class AIGraderConfigAdmin(admin.ModelAdmin):
    list_display = ("__str__", "enabled", "model", "image_detail", "updated_at")


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


# --- Admin dashboard (EPIC-8) ---

from .models import AlertEvent, AlertRule, CostRecord, DashboardSnapshot  # noqa: E402


@admin.register(DashboardSnapshot)
class DashboardSnapshotAdmin(admin.ModelAdmin):
    list_display = ("captured_at", "scope")
    list_filter = ("scope",)
    date_hierarchy = "captured_at"


@admin.register(CostRecord)
class CostRecordAdmin(admin.ModelAdmin):
    list_display = ("service", "period", "amount_usd", "source", "fetched_at")
    list_filter = ("source", "service", "period")


@admin.register(AlertRule)
class AlertRuleAdmin(admin.ModelAdmin):
    list_display = ("key", "label", "threshold", "enabled", "section")
    list_filter = ("enabled", "section")


@admin.register(AlertEvent)
class AlertEventAdmin(admin.ModelAdmin):
    list_display = ("created_at", "rule_key", "level", "message", "dismissed_at")
    list_filter = ("level", "rule_key", "section")
