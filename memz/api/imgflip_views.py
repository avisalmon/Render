"""Classic Imgflip templates in the solo creator (ACT-Z.5, spec §7.3).
Two endpoints: browsing the template list needs no account and no
throttle beyond the browser's own good sense (it's a cached, read-only
proxy of Imgflip's own public list); making a meme from one is exactly
the same shape as `MemeViewSet.create` — a guest may do it, same throttles,
same "identity from the request, never the body" rule (spec Rule 12.3.3.3).
"""

from rest_framework.permissions import AllowAny
from rest_framework.renderers import JSONRenderer
from rest_framework.response import Response
from rest_framework.views import APIView

from .. import imgflip_templates
from ..memes import make_meme_from_template
from .renderers import StaffOnlyBrowsableRenderer
from .serializers import MemeSerializer
from .throttles import MemeCreateAnonThrottle, MemeCreateUserThrottle

RENDERERS = [JSONRenderer, StaffOnlyBrowsableRenderer]


class ImgflipTemplatesView(APIView):
    """GET: the template picker's own list — id, name, a preview image URL,
    and box_count (v1 only ever fills the first two boxes, so the UI can
    grey out a third+ box rather than silently drop what's typed there)."""

    permission_classes = [AllowAny]
    renderer_classes = RENDERERS

    def get(self, request):
        templates = imgflip_templates.list_templates()
        out = [
            {"id": t.get("id"), "name": t.get("name"), "url": t.get("url"), "box_count": t.get("box_count")}
            for t in templates
        ]
        return Response({"templates": out, "available": imgflip_templates.is_configured()})


class ImgflipCaptionView(APIView):
    """POST {template_id, top_text, bottom_text} -> a new `Meme`, same
    response shape as `MemeViewSet.create` (spec §12.3's memes/ resource)."""

    permission_classes = [AllowAny]
    renderer_classes = RENDERERS
    throttle_classes = [MemeCreateAnonThrottle, MemeCreateUserThrottle]

    def post(self, request):
        template_id = request.data.get("template_id")
        if not template_id:
            return Response({"template_id": "צריך לבחור תבנית."}, status=400)

        user = request.user if request.user.is_authenticated else None
        try:
            meme = make_meme_from_template(
                template_id=template_id,
                top_text=request.data.get("top_text", ""),
                bottom_text=request.data.get("bottom_text", ""),
                user=user,
            )
        except imgflip_templates.ImgflipUnavailable as exc:
            return Response({"detail": str(exc)}, status=400)

        out = MemeSerializer(meme, context={"request": request})
        return Response(out.data, status=201, headers={"Location": f"/memz/m/{meme.share_slug}/"})
