from rest_framework import routers

from .api import ENDPOINTS
from .permissions import IsPlayer


class PlayerRoot(routers.APIRootView):
    permission_classes = [IsPlayer]


class PlayerRouter(routers.DefaultRouter):
    APIRootView = PlayerRoot
    include_format_suffixes = False


router = PlayerRouter()
for path, viewset in ENDPOINTS.items():
    router.register(path, viewset, basename=f"api-{path}")

urlpatterns = router.urls
