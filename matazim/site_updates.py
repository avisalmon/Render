"""REQ-M.184 - "what changed on the site", posted by the team, read by everybody.

Atid's list for the site asks for "עדכון שינויים באתר". A note is a row
(`SiteUpdate`); this module is the screens and the one act that tells people.

**Posting rings each person's bell once**, and only for the people the note is
for: the leaders and students of the posting institution, not the whole
installation (§4.4). The bell is a pointer to the list, never the only telling
(REQ-M.128): the list on `/matazim/updates/` and the card on a person's own home
carry the same words.
"""

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .access import institution_of, is_program_manager, visible_site_updates
from .models import Leader, Notification, SiteUpdate, Student
from .notify import notify
from .views import shell

LOGIN_URL = "/matazim/login/"


def announce(update, by):
    """Ring the bell of everyone in the posting institution, once each."""
    users = set(
        Leader.objects.filter(institution=update.institution).values_list("user_id", flat=True)
    ) | set(
        Student.objects.filter(leader__institution=update.institution)
        .values_list("user_id", flat=True)
    )
    users.discard(getattr(by, "id", None))
    from django.contrib.auth.models import User

    for person in User.objects.filter(pk__in=users):
        notify(person, Notification.SITE_UPDATE, update.title, url="/matazim/updates/", actor=by)


@login_required(login_url=LOGIN_URL)
def updates(request):
    """The list of what changed, newest first, pinned ones on top."""
    return render(
        request,
        "matazim/updates.html",
        shell(request, "updates", rows=list(visible_site_updates(request.user))),
    )


@login_required(login_url=LOGIN_URL)
def staff_updates(request):
    """Write a note about a change; see, fix and remove the ones already written."""
    if not is_program_manager(request.user):
        raise PermissionDenied

    error = ""
    if request.method == "POST":
        title = (request.POST.get("title") or "").strip()
        institution = institution_of(request.user)
        if not title:
            error = "צריך לכתוב מה השתנה."
        elif institution is None:
            raise PermissionDenied
        else:
            row = SiteUpdate.objects.create(
                institution=institution, title=title[:160],
                body=(request.POST.get("body") or "").strip(),
                pinned=request.POST.get("pinned") == "on", posted_by=request.user,
            )
            announce(row, by=request.user)
            return redirect("matazim:staff_updates")

    return render(
        request,
        "matazim/staff_updates.html",
        shell(request, "staff", rows=list(visible_site_updates(request.user)), error=error,
              posted=request.POST if request.method == "POST" else None),
    )


@require_POST
@login_required(login_url=LOGIN_URL)
def edit_update(request, update_id):
    if not is_program_manager(request.user):
        raise PermissionDenied
    row = get_object_or_404(visible_site_updates(request.user), pk=update_id)
    title = (request.POST.get("title") or "").strip()
    if title:
        row.title = title[:160]
        row.body = (request.POST.get("body") or "").strip()
        row.pinned = request.POST.get("pinned") == "on"
        row.save()
    return redirect("matazim:staff_updates")


@require_POST
@login_required(login_url=LOGIN_URL)
def delete_update(request, update_id):
    if not is_program_manager(request.user):
        raise PermissionDenied
    get_object_or_404(visible_site_updates(request.user), pk=update_id).delete()
    return redirect("matazim:staff_updates")
