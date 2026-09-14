"""The browsable API is a map of the product; in production it is for staff
(spec Rule 12.3.3.9). Everyone else gets JSON whatever they asked for,
rather than a 406, so a page's fetch() and a curious browser both work."""

from django.conf import settings
from rest_framework.renderers import BrowsableAPIRenderer, JSONRenderer


def browsing_allowed(request):
    user = getattr(request, "user", None)
    return bool(settings.DEBUG or (user is not None and user.is_authenticated and user.is_staff))


class StaffOnlyBrowsableRenderer(BrowsableAPIRenderer):
    def render(self, data, accepted_media_type=None, renderer_context=None):
        renderer_context = renderer_context or {}
        request = renderer_context.get("request")
        if request is not None and not browsing_allowed(request):
            response = renderer_context.get("response")
            if response is not None:
                response["Content-Type"] = "application/json"
            return JSONRenderer().render(data, "application/json", renderer_context)
        return super().render(data, accepted_media_type, renderer_context)
