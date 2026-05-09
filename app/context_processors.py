from django.conf import settings


def site_settings(request):
    return {
        "plausible_domain": getattr(settings, "PLAUSIBLE_DOMAIN", ""),
    }
