"""The public bank's own uploader (spec §6.6) — staff only.

ACT-Z.17, Avi: "another feature that will be only for the admin user.
Nobody will see this feature... it's not a user image bank, it's for the
general bank... I can just from my phone upload images as many as I want,
not as a normal user."

Deliberately a separate endpoint from `MemeImageViewSet.create`, not a
flag on it. That one writes a private image owned by the caller, under a
tier quota; this one writes `owner=None, visibility=PUBLIC` — the pool
every game in the world draws from (dealing.pool_for) — with no quota at
all. Keeping them apart means no request to the ordinary uploader can
ever be talked into reaching the public bank, whatever it sends.

What it does *not* skip is moderation. The public bank is the most
exposed surface memz has: one bad image there reaches strangers' phones
in rooms nobody here opened. The verdict is stored and shown, exactly as
for a normal upload (Rule 6.4.1 keeps anything unapproved out of play).
"""

from django.db import transaction
from django.utils.text import slugify
from rest_framework import status
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView

from ..models import MemeImage, Pack, PackImage
from .renderers import StaffOnlyBrowsableRenderer
from .serializers import MemeImageSerializer

from rest_framework.renderers import JSONRenderer

RENDERERS = [JSONRenderer, StaffOnlyBrowsableRenderer]

# The pack a bank upload lands in when none is named. A public pack *is*
# a category (models.Pack), so this is the categorisation Avi asked for
# ("you can categorize them as Avi's images, whatever") without inventing
# a second grouping concept next to the one the bank already has.
DEFAULT_PACK_NAME = "התמונות של אבי"


def _pack_for(name):
    """The public pack to file an upload under, created if it's new.
    Matched by name so the phone can keep typing the same one."""
    name = (name or "").strip() or DEFAULT_PACK_NAME
    pack = Pack.objects.filter(owner__isnull=True, is_public=True, name=name).first()
    if pack is not None:
        return pack
    base = slugify(name, allow_unicode=True) or "bank"
    slug, n = base, 2
    while Pack.objects.filter(slug=slug).exists():
        slug, n = f"{base}-{n}", n + 1
    return Pack.objects.create(
        name=name, slug=slug, owner=None, is_public=True,
        description="הועלה מהמסך של המנהל", order=100,
    )


class BankUploadView(APIView):
    """`POST /memz/api/bank/images/` — one image into the public bank.

    Staff only, and `IsAdminUser` is the whole gate: there is no object
    here whose ownership could stand in for permission."""

    permission_classes = [IsAdminUser]
    renderer_classes = RENDERERS

    def post(self, request):
        from .. import moderation, uploads

        serializer = MemeImageSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        raw_file = serializer.validated_data.pop("file")
        try:
            processed = uploads.process_upload(raw_file)
        except uploads.UploadError as exc:
            return Response({"file": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        verdict, note = moderation.check_image(processed)
        processed.seek(0)

        with transaction.atomic():
            pack = _pack_for(request.data.get("pack"))
            image = MemeImage(
                owner=None, visibility=MemeImage.PUBLIC,
                moderation_status=verdict, moderation_note=note,
                seed_key="", title=serializer.validated_data.get("title", ""),
            )
            image.file.save(raw_file.name, processed, save=True)
            PackImage.objects.create(pack=pack, image=image, order=pack.images.count())

        out = MemeImageSerializer(image).data
        out["pack"] = {"id": pack.id, "name": pack.name}
        return Response(out, status=status.HTTP_201_CREATED)


class BankImageView(APIView):
    """`DELETE /memz/api/bank/images/<pk>/` — take one back out.

    Scoped to public, unowned images on purpose: the bank screen must
    never become a way to reach into somebody's private uploads."""

    permission_classes = [IsAdminUser]
    renderer_classes = RENDERERS

    def delete(self, request, pk):
        image = MemeImage.objects.filter(
            pk=pk, owner__isnull=True, visibility=MemeImage.PUBLIC
        ).first()
        if image is None:
            return Response(status=status.HTTP_404_NOT_FOUND)
        image.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
