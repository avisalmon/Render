"""Who may read the curriculum, and who may change it.

SL-B1 recorded authoring as admin-only. A decision recorded in a backlog is
worth nothing unless something enforces it, and an API with eight CRUD
resources is precisely where "only staff author content" gets forgotten —
once, on the seventh resource, silently.

So it is one class, applied to every curriculum viewset, rather than a
`permission_classes` line written out eight times with one of them wrong.
"""

from rest_framework.permissions import SAFE_METHODS, BasePermission


class ReadAnyWriteStaff(BasePermission):
    """Signed-in people read; staff write.

    Read still requires an account: SensorLab is a course someone enrolled
    in, not a public library, and spec §1 has no anonymous mode.
    """

    message = "Only staff may author SensorLab content."

    def has_permission(self, request, view):
        user = getattr(request, "user", None)
        if not (user and user.is_authenticated):
            return False
        return request.method in SAFE_METHODS or bool(user.is_staff)
