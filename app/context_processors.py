from django.conf import settings


def site_settings(request):
    return {
        "plausible_domain": getattr(settings, "PLAUSIBLE_DOMAIN", ""),
        "whatsapp_number": getattr(settings, "WHATSAPP_NUMBER", "972500000000"),
    }
