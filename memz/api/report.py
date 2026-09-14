"""The report link on every share page (spec Rule 6.4.3): no in-app
moderation queue in v1, just a mail to the site admin naming the slug.
Silently a no-op for a slug that doesn't exist, rather than confirming or
denying it — the same reasoning as the share page itself (spec Rule
8.2.2): a stranger probing slugs learns nothing either way."""

from django.conf import settings
from django.core.mail import send_mail
from rest_framework.permissions import AllowAny
from rest_framework.renderers import JSONRenderer
from rest_framework.response import Response
from rest_framework.views import APIView

from ..models import Meme
from .throttles import ReportThrottle


class ReportView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [ReportThrottle]
    renderer_classes = [JSONRenderer]

    def post(self, request):
        slug = str(request.data.get("slug", "")).strip()
        meme = Meme.objects.filter(share_slug=slug).first() if slug else None
        if meme is not None:
            admin_email = getattr(settings, "SECURITY_OWNER_EMAIL", "") or settings.DEFAULT_FROM_EMAIL
            send_mail(
                subject="memz: meme reported",
                message=f"A meme was reported.\n\nSlug: {meme.share_slug}\nLink: /memz/m/{meme.share_slug}/",
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[admin_email],
                fail_silently=True,
            )
        return Response({"ok": True})
