from rest_framework import serializers

from ..models import Profile


class ProfileSerializer(serializers.ModelSerializer):
    # Accept a precise point from a phone and let Profile.save() round it,
    # rather than refusing it: the rounding is the guarantee, not the input.
    area_lat = serializers.DecimalField(max_digits=10, decimal_places=7, required=False, allow_null=True)
    area_lng = serializers.DecimalField(max_digits=10, decimal_places=7, required=False, allow_null=True)

    class Meta:
        model = Profile
        fields = ["id", "display_name", "language", "tier", "area_name", "area_lat", "area_lng", "radius_km",
                  "is_adult_confirmed", "accepted_terms_at", "profile_public", "show_points_public",
                  "theme", "palette", "shelf_view", "created_at"]
        # The tier is what a person may do; nobody sets their own (spec 12.11).
        # Age and terms are set once, by onboarding.
        read_only_fields = ["tier", "is_adult_confirmed", "accepted_terms_at", "created_at"]
