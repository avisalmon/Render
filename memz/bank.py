"""What a given caller may see and deal from the meme bank (spec §6.5).
Shared by the solo creator's form and its API twin, so the rule lives in
exactly one place."""

from django.db.models import Q

from .models import MemeImage


def images_for(user):
    """Approved images a caller may use: the public bank always, plus their
    own (any moderation status — they need to see a pending upload's status
    too) when logged in. `user` may be `None` or `AnonymousUser`."""
    public = Q(owner__isnull=True, visibility=MemeImage.PUBLIC, moderation_status=MemeImage.APPROVED)
    if user is None or not getattr(user, "is_authenticated", False):
        return MemeImage.objects.filter(public)
    return MemeImage.objects.filter(public | Q(owner=user, moderation_status=MemeImage.APPROVED))
