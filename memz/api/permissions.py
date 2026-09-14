"""Object-level rules (spec Rule 12.3.3.2).

Reading is open to whoever the queryset already let see the row (own rows
and public rows). Changing or deleting is for the owner; public rows, which
have no owner, are for staff. A row the queryset hides is a 404 before this
class is ever asked, so a stranger's private things do not exist as far as
the API can tell.
"""

from rest_framework.permissions import SAFE_METHODS, BasePermission


class IsOwnerOrPublicReadOnly(BasePermission):
    message = "זה לא שלך."

    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return True
        owner_id = view.owner_id_of(obj)
        if owner_id is not None:
            return owner_id == request.user.id
        return bool(request.user.is_staff)
