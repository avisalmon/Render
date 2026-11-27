"""The one paragraph about an institution (Epic P, sprint P.2).

Avi, 2026-11-27: under the name, "a big paragraph with the main points: where
it is geographically, the main areas of learning, the research focuses". The
paragraph is written by a model from the institution's own reference
overview page and nothing else, so it adds no fact the reference does not
hold; it is marked with that source and date, and an institution without a
page gets no paragraph. One call per institution, once; without a key the
stub writes nothing, so the import never invents a paragraph.
"""
import logging
from decimal import Decimal

from django.conf import settings

from . import reference_pages as pages

log = logging.getLogger(__name__)
PROMPT = (
    "אתה כותב פסקה אחת בעברית על מוסד אקדמי בישראל, לעמוד ציבורי. "
    "השתמש אך ורק במידע שבטקסט המצורף; אל תוסיף עובדה, מספר או שם שאינם בו, ואל תשתמש בסופרלטיבים שאינם בו. "
    "הפסקה עונה על שלוש שאלות, בסדר הזה: איפה המוסד נמצא ומה הוא (סוג, ותק, קמפוסים), מה לומדים בו בעיקר "
    "(תחומי הלימוד המרכזיים), ובמה המחקר שלו מתמקד או ידוע. "
    "אורך: 90 עד 140 מילים, פסקה אחת, בלי כותרת, בלי רשימות, בלי אמוג'י, בלי מקפים ארוכים, בלי ציטוט של מקורות. "
    "כתוב בגוף שלישי, בלשון עניינית ונעימה לקריאה, כמו ערך מבוא טוב."
)


def _key():
    return getattr(settings, "OPENAI_API_KEY", "") or ""


def _model():
    return getattr(settings, "ACADEMIA360_IDENTITY_MODEL", "") or getattr(settings, "OPENAI_DEFAULT_MODEL", "gpt-4o-mini")


def page_text(page_html, limit=9000):
    """The overview page as plain text: the sections' paragraphs, the facts,
    the timeline. Capped, so one institution is one modest call."""
    o = pages.read_overview(page_html)
    parts = []
    if o["tagline"]:
        parts.append(o["tagline"])
    for key, value, approx, year, label in o["facts"]:
        parts.append(f"{label}: {'כ-' if approx else ''}{value}")
    for title, kind, text in o["sections"]:
        parts.append(f"## {title}\n{text}")
    if o["timeline"]:
        parts.append("ציוני דרך: " + "; ".join(f"{y}: {t}" for y, t in o["timeline"][:12]))
    return "\n\n".join(parts)[:limit]


def write(inst_name, page_html):
    """-> (paragraph, usage dict). ('', {}) when there is no key or no text."""
    text = page_text(page_html)
    if len(text) < 200:
        return "", {"skipped": "too little text"}
    if not _key():
        return "", {"skipped": "no key"}
    from openai import OpenAI

    client = OpenAI(api_key=_key(), timeout=120)
    model = _model()
    r = client.responses.create(model=model, input=[
        {"role": "system", "content": PROMPT},
        {"role": "user", "content": f"המוסד: {inst_name}\n\nהטקסט:\n{text}"},
    ])
    out = (getattr(r, "output_text", "") or "").strip()
    u = getattr(r, "usage", None)
    usage = {"model": model, "tokens_in": getattr(u, "input_tokens", 0) or 0,
             "tokens_out": getattr(u, "output_tokens", 0) or 0}
    usage["cost_usd"] = cost(model, usage["tokens_in"], usage["tokens_out"])
    words = len(out.split())
    if words < 40 or words > 220 or "\n\n" in out:
        log.warning("identity for %s came back odd (%s words); kept anyway for review", inst_name, words)
    return out, usage


# $ per million tokens (input, output); unknown models take the first row
PRICES = {"gpt-4o-mini": (Decimal("0.15"), Decimal("0.60")), "gpt-6-luna": (Decimal("0.10"), Decimal("0.50")),
          "gpt-6.1-terra": (Decimal("1.00"), Decimal("5.00"))}


def cost(model, tokens_in, tokens_out):
    pin, pout = PRICES.get(model, PRICES["gpt-6.1-terra"])
    return ((Decimal(tokens_in) * pin + Decimal(tokens_out) * pout) / Decimal(1_000_000)).quantize(Decimal("0.00001"))
