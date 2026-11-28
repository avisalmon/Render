"""Writing a challenge with AI (spec 14): the creator's conversations.

Creators and curators only (`access.may_write`); a conversation is its
author's alone, anyone else gets the app's 404. Every write is a plain POST
with a redirect back, like the editor; while an answer is being written the
page polls one small JSON route and reloads when it is done.
"""

from django.contrib import messages
from django.http import FileResponse, Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_POST

from . import access, ai
from .models import Idea, IdeaMessage

MAX_TEXT = 4000


def _creator(request):
    access.profile_for(request.user)
    if not access.may_write(request.user):
        raise Http404


def _idea(request, pk):
    _creator(request)
    return get_object_or_404(Idea.objects.select_related("experience"), pk=pk, author=request.user)


@access.signed_in
@ensure_csrf_cookie
def ideas(request):
    _creator(request)
    return render(request, "breakout/ideas.html", {
        "section": "ideas",
        "ideas": Idea.objects.filter(author=request.user).select_related("experience"),
    })


@access.signed_in
@require_POST
def idea_new(request):
    _creator(request)
    idea = Idea.objects.create(author=request.user)
    return redirect("breakout:idea", idea.pk)


@access.signed_in
@ensure_csrf_cookie
def idea(request, pk):
    idea = _idea(request, pk)
    thinking = ai.busy(idea)
    return render(request, "breakout/idea.html", {
        "section": "ideas",
        "idea": idea,
        "chat": list(idea.messages.all()),
        "thinking": thinking,
        "stop": ai.over_cap(request.user),
        "stub": ai.stub_mode(),
    })


@access.signed_in
@require_POST
def idea_say(request, pk):
    idea = _idea(request, pk)
    said = (request.POST.get("text") or "").strip()[:MAX_TEXT]
    uploaded = request.FILES.get("picture")
    if ai.busy(idea):
        messages.info(request, "רגע, התשובה הקודמת עוד נכתבת.")
        return redirect("breakout:idea", idea.pk)
    if not said and not uploaded:
        messages.error(request, "כתבו משהו, או צרפו סקיצה.")
        return redirect("breakout:idea", idea.pk)
    picture = None
    if uploaded:
        picture, error = ai.prepared_picture(uploaded)
        if error:
            messages.error(request, error)
            return redirect("breakout:idea", idea.pk)
    ai.say(idea, said, picture)
    return redirect(f"/breakout/ideas/{idea.pk}/#br-chat-end")


@access.signed_in
@require_POST
def idea_build(request, pk):
    idea = _idea(request, pk)
    if idea.experience_id:
        return redirect("breakout:edit", idea.experience.slug)
    if not idea.ready:
        messages.error(request, "עוד חסרים נושא ותוכנית תחנות בכרטיס. ספרו לי עוד, ואז נבנה.")
        return redirect("breakout:idea", idea.pk)
    if ai.busy(idea):
        return redirect("breakout:idea", idea.pk)
    ai.build(idea)
    return redirect(f"/breakout/ideas/{idea.pk}/#br-chat-end")


@access.signed_in
def idea_status(request, pk):
    idea = _idea(request, pk)
    return JsonResponse({"thinking": ai.busy(idea)})


@access.signed_in
@require_POST
def idea_changes(request, pk, msg_pk):
    idea = _idea(request, pk)
    msg = get_object_or_404(IdeaMessage, pk=msg_pk, idea=idea, changes_state=IdeaMessage.PENDING)
    if idea.experience is None:
        raise Http404
    if request.POST.get("action") == "apply":
        ai.apply_changes(msg)
        messages.success(request, "השינויים נכנסו לאתגר.")
    else:
        ai.decline_changes(msg)
        messages.info(request, "ההצעה נדחתה. שום דבר לא השתנה.")
    return redirect(f"/breakout/ideas/{idea.pk}/#br-chat-end")


@access.signed_in
@require_POST
def idea_delete(request, pk):
    """The conversation goes; a challenge it built stays, it is the teacher's draft."""
    idea = _idea(request, pk)
    for m in idea.messages.exclude(picture=""):
        m.picture.delete(save=False)
    idea.delete()
    messages.success(request, "השיחה נמחקה.")
    return redirect("breakout:ideas")


@access.signed_in
def idea_picture(request, pk, msg_pk):
    idea = _idea(request, pk)
    msg = get_object_or_404(IdeaMessage, pk=msg_pk, idea=idea)
    if not msg.picture:
        raise Http404
    response = FileResponse(msg.picture.open("rb"), content_type="image/jpeg")
    response["X-Content-Type-Options"] = "nosniff"
    response["Cache-Control"] = "private, max-age=3600"
    return response
