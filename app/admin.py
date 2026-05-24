from django.contrib import admin

from .models import (
    ChatMessage,
    ChatSession,
    CopilotSeat,
    CorporateLead,
    Course,
    Entitlement,
    ModerationLog,
    NewsletterSubscriber,
    Note,
    SeatEvent,
    SystemPrompt,
    UsageLog,
    UserVideoProgress,
    Video,
)

admin.site.register(Note)
admin.site.register(Course)
admin.site.register(Video)
admin.site.register(UserVideoProgress)
admin.site.register(Entitlement)
admin.site.register(CopilotSeat)
admin.site.register(SeatEvent)
admin.site.register(SystemPrompt)
admin.site.register(ChatSession)
admin.site.register(ChatMessage)
admin.site.register(UsageLog)
admin.site.register(ModerationLog)


@admin.register(NewsletterSubscriber)
class NewsletterSubscriberAdmin(admin.ModelAdmin):
    list_display = ("email", "language", "source_page", "confirmed_at", "unsubscribed_at", "created_at")
    list_filter = ("language", "confirmed_at", "unsubscribed_at", "created_at")
    search_fields = ("email", "name", "source_page", "utm_source", "utm_campaign")
    readonly_fields = ("created_at", "updated_at", "ip_hash")


@admin.register(CorporateLead)
class CorporateLeadAdmin(admin.ModelAdmin):
    list_display = ("name", "company", "training_type", "team_size", "status", "created_at")
    list_filter = ("status", "training_type", "team_size", "created_at")
    search_fields = ("name", "company", "role", "message")
    readonly_fields = ("created_at", "ip_hash", "source_page", "referrer_url")
