from rest_framework.permissions import SAFE_METHODS, BasePermission

from ..access import profile_for


class HasBooksProfile(BasePermission):
    """Signed in and onboarded. Every Books endpoint starts here; querysets
    then scope to the caller, so nobody reaches another person's rows."""

    def has_permission(self, request, view):
        return profile_for(request.user) is not None


class CatalogueWrite(BasePermission):
    """The shared catalogue (BK2): anyone onboarded may read and may add a
    record; changing one takes a curator (staff), or the person who added
    it while it is still unverified; deleting takes a curator."""

    def has_permission(self, request, view):
        return profile_for(request.user) is not None

    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return True
        if request.user.is_staff:
            return True
        if request.method == "DELETE":
            return False
        owner = getattr(obj, "created_by", None)
        verified = getattr(obj, "is_verified", True)
        return owner is not None and owner == profile_for(request.user) and not verified


class StaffWrite(BasePermission):
    """Read for the onboarded, write for staff (tags, creators)."""

    def has_permission(self, request, view):
        if profile_for(request.user) is None:
            return False
        return request.method in SAFE_METHODS or request.user.is_staff
