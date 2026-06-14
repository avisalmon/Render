"""Chat views (EPIC-6.6). Read-public channels; posting requires login and goes
through the community guidelines/moderation/rate-limit pipeline."""
from urllib.parse import quote

from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render

from .chat import ensure_topic_channels, post_message
from .community import accept_guidelines, guidelines_accepted
from .models import Channel, ChannelMessage


def chat_home(request):
    """List the channels (topic / course / hackathon), grouped (REQ-6.6.1),
    with per-channel unread badges for logged-in members (REQ-6.6.6)."""
    ensure_topic_channels()
    from .chat import unread_count
    channels = list(Channel.objects.all())
    if request.user.is_authenticated:
        for ch in channels:
            ch.unread = unread_count(request.user, ch)
    return render(request, "app/community/chat_home.html", {
        "topic": [c for c in channels if c.kind == "topic"],
        "course": [c for c in channels if c.kind == "course"],
        "hackathon": [c for c in channels if c.kind == "hackathon"],
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
    if request.user.is_authenticated and not q:
        from .chat import mark_read
        mark_read(request.user, channel)
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


def promote_message(request, message_id):
    """REQ-6.6.5: promote a channel message into a forum thread or a tip.
    Allowed for the message author or staff. Pre-filled + linked back."""
    msg = get_object_or_404(ChannelMessage.objects.select_related("channel", "author"),
                            pk=message_id)
    if not request.user.is_authenticated:
        return redirect(f"/join/?next={quote(request.get_full_path())}")
    if request.user != msg.author and not request.user.is_staff:
        from django.http import HttpResponseForbidden
        return HttpResponseForbidden("רק כותב/ת ההודעה או צוות יכולים לקדם אותה")
    target = request.POST.get("target", "forum")
    back = f"\n\n— מתוך הצ'אט «{msg.channel.title}» (/community/chat/{msg.channel.slug}/)"
    if target == "tip":
        from .models import Tip
        tip = Tip.objects.create(author=msg.author, body=(msg.body + back)[:2000],
                                 tags=[msg.channel.domain] if msg.channel.domain else [])
        messages.success(request, "ההודעה הפכה לטיפ! 💡")
        return redirect("tip_detail", tip_id=tip.pk)
    from .models import ForumThread
    title = msg.body.strip().split("\n")[0][:120] or "מתוך הצ'אט"
    th = ForumThread.objects.create(
        category=msg.channel.domain or "general", kind="discussion",
        title=title, body=msg.body + back, author=msg.author,
        tags=[msg.channel.domain] if msg.channel.domain else [])
    messages.success(request, "ההודעה הפכה לדיון בפורום! 📌")
    return redirect("forum_thread", thread_id=th.pk)


def report_message(request, message_id):
    """REQ-6.6.6: report a message → the staff queue."""
    msg = get_object_or_404(ChannelMessage, pk=message_id)
    if not request.user.is_authenticated:
        return redirect(f"/join/?next={quote(request.get_full_path())}")
    if request.method == "POST":
        from .models import ContentReport
        ContentReport.objects.create(
            reporter=request.user, content_type="channel_message", object_id=msg.pk,
            reason=(request.POST.get("reason") or "").strip()[:300] or "דווח מהצ'אט")
        messages.success(request, "הדיווח נשלח לצוות. תודה.")
    return redirect("channel_view", slug=msg.channel.slug)


def hide_message(request, message_id):
    """REQ-6.6.6: staff hide a message."""
    msg = get_object_or_404(ChannelMessage, pk=message_id)
    if not request.user.is_authenticated or not request.user.is_staff:
        from django.http import HttpResponseForbidden
        return HttpResponseForbidden("פעולת צוות בלבד")
    if request.method == "POST":
        msg.is_hidden = True
        msg.save(update_fields=["is_hidden"])
        messages.success(request, "ההודעה הוסתרה.")
    return redirect("channel_view", slug=msg.channel.slug)


def channel_messages_api(request, slug):
    """Polling endpoint (REQ-6.6.1): JSON of messages, optionally after an id."""
    channel = get_object_or_404(Channel, slug=slug)
    msgs = channel.messages.filter(is_hidden=False).select_related("author__profile")
    after = request.GET.get("after")
    if after and after.isdigit():
        msgs = msgs.filter(pk__gt=int(after))
    return JsonResponse({"messages": [_msg_dict(m) for m in msgs[:100]]})
