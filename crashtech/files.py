"""A submission's file, to whoever may open it (security review, 2026-10-24:
the raw /media/ path handed it to anyone). The team that made it, anyone
with a role on the event, the site's staff; and everyone once the event is
in its museum, where the files are shown on purpose."""

from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404

from .models import SubmissionFile, TeamMembership
from .roles import roles_for


def can_open(user, sf):
    hackathon = sf.submission.challenge.hackathon
    if getattr(hackathon, "phase", "") == "museum":
        return True
    if not getattr(user, "is_authenticated", False):
        return False
    if user.is_staff or user.is_superuser or roles_for(user, hackathon):
        return True
    return TeamMembership.objects.filter(team=sf.submission.team, user=user).exists()


def submission_file(request, pk):
    sf = get_object_or_404(SubmissionFile.objects.select_related("submission__team", "submission__challenge__hackathon"), pk=pk)
    if not sf.file or not can_open(request.user, sf):
        raise Http404
    return FileResponse(sf.file.open("rb"), filename=sf.file.name.rsplit("/", 1)[-1])
