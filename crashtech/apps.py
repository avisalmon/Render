from django.apps import AppConfig


class CrashtechConfig(AppConfig):
    """CrashTech - a platform for running hardware hackathons, and for
    studying what happens at them (docs/crashtech/spec.md).

    Its own app, the same reasoning as matazim, memz and sensorlab: own
    models, own migrations, own URLs, own templates, own base template and
    own authentication screens. The only thing it shares with the rest of
    the project is the `auth.User` table, for sign-in (spec Rule 2.1.1).

    One deliberate exception to the usual isolation, stated by Avi and
    recorded as Rule 2.2.3: babook's portal links *in* to CrashTech,
    because this is a public production product people are routed to.
    CrashTech still links nowhere out.
    """

    default_auto_field = "django.db.models.BigAutoField"
    name = "crashtech"
    verbose_name = "CrashTech"
