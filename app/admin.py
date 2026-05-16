from django.contrib import admin

from .models import CopilotSeat, Course, Note, SeatEvent, UserVideoProgress, Video

admin.site.register(Note)
admin.site.register(Course)
admin.site.register(Video)
admin.site.register(UserVideoProgress)
admin.site.register(CopilotSeat)
admin.site.register(SeatEvent)
