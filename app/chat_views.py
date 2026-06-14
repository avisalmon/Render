"""Chat views (EPIC-6.6). Read-public channels; posting requires login and goes
through the community guidelines/moderation/rate-limit pipeline."""
from urllib.parse import quote

from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render

from .chat import ensure_topic_channels, post_message
from .community import accept_guidelines, guidelines_accepted
from .models import Channel


def chat_home(request):
    """List the channels (topic / course / hackathon), grouped (REQ-6.6.1)."""
    ensure_topic_channels()
    channels = Channel.objects.all()
    return render(request, "app/community/chat_home.html", {
        "topic": channels.filter(kind="topic"),
        "course": channels.filter(kind="course"),
        "hackathon": channels.filter(kind="hackathon"),
    })


def _msg_dict(m):
    return {
        "id": m.pk,
        "author": m.author.profile.public_name,
        "body": m.body,
        "at": m.created_at.strftime("%H:%M"),
    }


def course_channel(request, slug):
    """REQ-6.6.2: open (creating on demand) a course's cohort channel."""
    from .chat import channel_for_course
    from .models import Course
    course = get_object_or_404(Course, slug=slug)
    ch = channel_for_course(course)
    return redirect("channel_view", slug=ch.slug)


def channel_view(request, slug):
    """Channel page: history (searchable) + post box. POST creates a message."""
    channel = get_object_or_404(Channel, slug=slug)
    if request.method == "POST":
        if not request.user.is_authenticated:
            return redirect(f"/join/?next={quote(request.get_full_path())}")
        if request.POST.get("accept_guidelines"):
            accept_guidelines(request.user)
        msg, err = post_message(request.user, channel, request.POST.get("body"))
        if err == "guidelines":
            messages.error(request, "כדי לכתוב בצ'אט, סמנו שקראתם את כללי הקהילה")
        elif err:
            messages.error(request, err)
        return redirect("channel_view", slug=slug)

    q = (request.GET.get("q") or "").strip()
    msgs = channel.messages.filter(is_hidden=False).select_related("author__profile")
    if q:
        msgs = msgs.filter(body__icontains=q)
    msgs = list(msgs[:200])
    presence = []
    if channel.kind == "course" and channel.course_id:
        from .chat import learners_now
        presence = learners_now(channel.course)
    return render(request, "app/community/channel.html", {
        "channel": channel, "messages_list": msgs, "q": q,
        "needs_guidelines": request.user.is_authenticated and not guidelines_accepted(request.user),
        "last_id": msgs[-1].pk if msgs else 0,
        "presence": presence,
    })


def channel_messages_api(request, slug):
    """Polling endpoint (REQ-6.6.1): JSON of messages, optionally after an id."""
    channel = get_object_or_404(Channel, slug=slug)
    msgs = channel.messages.filter(is_hidden=False).select_related("author__profile")
    after = request.GET.get("after")
    if after and after.isdigit():
        msgs = msgs.filter(pk__gt=int(after))
    return JsonResponse({"messages": [_msg_dict(m) for m in msgs[:100]]})
