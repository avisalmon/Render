"""The bell, and what is behind it.

REQ-M.33. One screen and one action.

Reading a notification takes you to the thing itself, which is the only reason
the row exists: it is a pointer, and a pointer you cannot follow is a worse
version of an email. So opening the list marks everything read, and each row
links to the screen where the actual thing lives.

Marking read on open rather than per row, deliberately. A bell whose count only
clears when you click each line individually is a bell people stop opening, and
nothing here is lost by reading it: REQ-M.128 says every one of these also
appears on the screen it belongs to.
"""

from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .models import Notification
from .views import shell

LOGIN_URL = "/matazim/login/"


@login_required(login_url=LOGIN_URL)
def notices(request):
    """REQ-M.33 — what happened, newest first."""
    rows = list(Notification.objects.filter(user=request.user)[:60])

    # Read once it has been looked at. Done after the list is materialised so
    # the page can still show which ones were new when it opened, which is the
    # difference between a list and a list you can read.
    unread = [row.pk for row in rows if row.is_unread]
    if unread:
        Notification.objects.filter(pk__in=unread).update(read_at=timezone.now())

    return render(
        request,
        "matazim/notices.html",
        shell(request, "notices", notices=rows, was_unread=set(unread)),
    )


@require_POST
@login_required(login_url=LOGIN_URL)
def clear_notices(request):
    """Somebody who wants the count gone without reading each one."""
    Notification.objects.filter(user=request.user, read_at__isnull=True).update(
        read_at=timezone.now()
    )
    return redirect("matazim:notices")
