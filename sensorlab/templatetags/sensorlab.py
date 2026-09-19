"""SensorLab's template tags.

`{% chart %}…{% endchart %}` exists so spec §7.7 lives in the component
rather than in every caller's memory. The rule is that the chrome mirrors
in Hebrew and the *data* does not: axes still run left to right, numerals
stay Latin, notation stays LTR. Mirroring a velocity-versus-time chart does
not localise it, it makes the physics wrong.

`{% t "key" %}` reads SensorLab's own copy in whichever language the
request is running under (see `sensorlab/strings.py` for why this is not
gettext).
"""

from django import template
from django.utils.safestring import mark_safe

from ..strings import DEFAULT_LANGUAGE
from ..strings import text as lookup

register = template.Library()


@register.simple_tag(takes_context=True)
def t(context, key):
    """One interface string, in the request's language."""
    request = context.get("request")
    language = getattr(request, "sensorlab_language", DEFAULT_LANGUAGE)
    return lookup(key, language)


@register.filter
def sensor_name(key):
    """A sensor's name in the active language.

    A filter rather than something the view prepares, so no view can hand a
    template an English label again — which is exactly how the sensors screen
    came to tell Hebrew readers "Accelerometer" (fixed in SL-B4). The active
    language is the request's, set by `SensorLabLanguageMiddleware`.
    """
    from django.utils import translation

    language = translation.get_language() or DEFAULT_LANGUAGE
    return lookup(f"sensor.{key}", "he" if str(language).startswith("he") else "en") or key


@register.tag(name="chart")
def chart(parser, token):
    """Wrap chart markup in SensorLab's chart frame, always LTR.

    Usage::

        {% chart %}<svg viewBox="0 0 320 200">…</svg>{% endchart %}
        {% chart "Free fall — measured against your prediction" %}…{% endchart %}
    """
    bits = token.split_contents()
    label = parser.compile_filter(bits[1]) if len(bits) > 1 else None
    nodelist = parser.parse(("endchart",))
    parser.delete_first_token()
    return ChartNode(nodelist, label)


class ChartNode(template.Node):
    def __init__(self, nodelist, label):
        self.nodelist = nodelist
        self.label = label

    def render(self, context):
        inner = self.nodelist.render(context)
        label = self.label.resolve(context) if self.label else ""
        caption = f'<figcaption class="sl-muted">{label}</figcaption>' if label else ""
        # dir="ltr" is not optional and not the caller's business — §7.7.
        return mark_safe(
            f'<figure class="sl-chart" data-component="chart" dir="ltr">{inner}{caption}</figure>'
        )
