"""The certificate: the thing a certified מט״צ can actually show somebody.

REQ-M.20 and REQ-M.28. Two pages with opposite audiences, which is the whole
design problem.

**`my_certificate`** is for the member, behind their login, built to print.

**`verify`** is for a stranger. A school checking a certificate is not a member
and never will be, so that page is public on purpose. And the person named on it
is a minor, so §4.10 governs what a stranger gets: the name, the date, and
whether it is valid. Not their school, not their leader, not their email, and
nothing that lets the identifier be walked to find other children.

A certificate is a *current* fact rather than a permanent one, because
certification is revocable (REQ-M.78). A printed copy outlives a revocation,
which cannot be helped; the page somebody checks against says what is true when
they ask. Withdrawn is a different answer from not found, and the difference
matters to whoever is holding the paper.
"""

from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from .models import MatazCertificate, Student
from .views import shell

LOGIN_URL = "/matazim/login/"


@login_required(login_url=LOGIN_URL)
def my_certificate(request):
    """REQ-M.20, REQ-M.28 — their own, built from `request.user` and nothing else."""
    student = (
        Student.objects.filter(user=request.user, status=Student.CERTIFIED)
        .order_by("-cohort_year")
        .first()
    )
    certificate = (
        MatazCertificate.objects.filter(student=student, revoked_at__isnull=True).first()
        if student
        else None
    )
    if certificate is None:
        # Not an error: they simply are not certified yet, and the path screen
        # says what is still outstanding (REQ-M.77).
        return render(
            request,
            "matazim/certificate_none.html",
            shell(request, "path"),
            status=404,
        )

    return render(
        request,
        "matazim/certificate.html",
        shell(request, "path", certificate=certificate, student=student),
    )


def verify(request, public_id):
    """REQ-M.20 — public, deliberately, and deliberately thin.

    No login: a school checking a certificate has no account. No extra detail: a
    stranger who typed a URL has no business learning a child's school or who
    teaches them.
    """
    certificate = MatazCertificate.objects.filter(public_id=public_id).first()
    return render(
        request,
        "matazim/verify.html",
        shell(request, "verify", certificate=certificate),
    )
