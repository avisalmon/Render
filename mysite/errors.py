"""Project-wide error handler dispatch.

Django only allows one handler403/404/500 for the whole project, but the
isolated sub-products (matazim, ustrip, memz, sensorlab) each need their own error
pages so none leaks babook's chrome into their walls (REQ-M.2; ustrip spec
§1; memz spec §12.1). This composes them by path prefix rather than teaching
any app about another — they stay unaware of each other's existence,
exactly as their own specs require. Anything outside every prefix falls
through to Django's own defaults, which is what renders babook's own
404.html/500.html.
"""

from django.views import defaults

from matazim import errors as matazim_errors
from memz import errors as memz_errors
from sensorlab import errors as sensorlab_errors
from ustrip import errors as ustrip_errors


def page_not_found(request, exception=None):
    if request.path.startswith(matazim_errors.PREFIX):
        return matazim_errors.page_not_found(request, exception)
    if request.path.startswith(ustrip_errors.PREFIX):
        return ustrip_errors.page_not_found(request, exception)
    if request.path.startswith(memz_errors.PREFIX):
        return memz_errors.page_not_found(request, exception)
    if request.path.startswith(sensorlab_errors.PREFIX):
        return sensorlab_errors.page_not_found(request, exception)
    return defaults.page_not_found(request, exception)


def server_error(request):
    if request.path.startswith(matazim_errors.PREFIX):
        return matazim_errors.server_error(request)
    if request.path.startswith(ustrip_errors.PREFIX):
        return ustrip_errors.server_error(request)
    if request.path.startswith(memz_errors.PREFIX):
        return memz_errors.server_error(request)
    if request.path.startswith(sensorlab_errors.PREFIX):
        return sensorlab_errors.server_error(request)
    return defaults.server_error(request)


def permission_denied(request, exception=None):
    # ustrip has no handler403 of its own — its family-group gate renders
    # its own access-denied page directly rather than raising (access.py).
    if request.path.startswith(matazim_errors.PREFIX):
        return matazim_errors.permission_denied(request, exception)
    if request.path.startswith(memz_errors.PREFIX):
        return memz_errors.permission_denied(request, exception)
    if request.path.startswith(sensorlab_errors.PREFIX):
        return sensorlab_errors.permission_denied(request, exception)
    return defaults.permission_denied(request, exception)
