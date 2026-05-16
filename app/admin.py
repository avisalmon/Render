from django.contrib import admin
from .models import Note, Course, Video, UserVideoProgress

admin.site.register(Note)
admin.site.register(Course)
admin.site.register(Video)
admin.site.register(UserVideoProgress)
