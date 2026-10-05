from django.urls import path
from rest_framework import routers

from .api import ENDPOINTS, SINGLETONS
from .permissions import IsPlayer


class PlayerRoot(routers.APIRootView):
    permission_classes = [IsPlayer]


class PlayerRouter(routers.DefaultRouter):
    APIRootView = PlayerRoot
    include_format_suffixes = False


router = PlayerRouter()
for prefix, viewset in ENDPOINTS.items():
    router.register(prefix, viewset, basename=f"api-{prefix}")

urlpatterns = router.urls + [
    path(f"{name}/", view.as_view(), name=f"api-{name}") for name, view in SINGLETONS.items()
]
