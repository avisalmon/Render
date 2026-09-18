"""SensorLab's template tags.

`{% chart %}…{% endchart %}` exists so spec §7.7 lives in the component
rather than in every caller's memory. The rule is that the chrome mirrors
in Hebrew and the *data* does not: axes still run left to right, numerals
stay Latin, notation stays LTR. Mirroring a velocity-versus-time chart does
not localise it, it makes the physics wrong.

Wrapping the markup by hand would mean remembering `dir="ltr"` on every
chart in every lab, forever, and being right every time. This tag remembers
instead, and a test asserts every chart on the page carries it.
"""

from django import template
from django.utils.safestring import mark_safe

register = template.Library()


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
