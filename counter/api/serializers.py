from rest_framework import serializers

from ..models import Event, Page, Promo, PromoPlacement, Site


class SiteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Site
        fields = ["id", "name", "key", "base_url", "repo", "local_path", "is_active",
                  "snippet_installed_at", "created_at"]
        read_only_fields = ["key", "created_at"]


class PageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Page
        fields = ["id", "site", "path", "title", "first_seen", "last_seen"]
        read_only_fields = ["first_seen", "last_seen"]


class EventSerializer(serializers.ModelSerializer):
    class Meta:
        model = Event
        fields = ["id", "site", "page", "kind", "name", "visitor_id", "referrer", "promo", "created_at"]
        read_only_fields = ["created_at"]


class PromoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Promo
        fields = ["id", "title", "text", "url", "image_url", "is_active", "created_at"]
        read_only_fields = ["created_at"]


class PromoPlacementSerializer(serializers.ModelSerializer):
    class Meta:
        model = PromoPlacement
        fields = ["id", "promo", "site", "path_prefix", "weight", "is_active"]
