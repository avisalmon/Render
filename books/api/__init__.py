from rest_framework.routers import DefaultRouter

from .viewsets import ProfileViewSet

router = DefaultRouter()
router.register("profiles", ProfileViewSet, basename="profile")
