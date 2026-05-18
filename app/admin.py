from django.contrib import admin

from .models import (
    ChatMessage,
    ChatSession,
    CopilotSeat,
    Course,
    Entitlement,
    ModerationLog,
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
