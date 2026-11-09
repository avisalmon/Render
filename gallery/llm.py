"""gallery's one door to a language model (REQ-G.51 to G.56, G.63, G.64).

Only the skill chat comes through here (REQ-G.104: no other screen calls a
model). Same shape as `design3d/llm.py`, copied, not imported (Rule 2): the
Responses API, a price table, JSON answers, and a stub without a key so the
screens and the tests never need a bill.

Every call is priced before it is made from a generous estimate of its tokens,
so the chat can stop *before* the call that would cross its 40 cents
(REQ-G.63), and is recorded after with its real tokens (REQ-G.64).
"""

import json
import logging
import re
from decimal import Decimal

from django.conf import settings

log = logging.getLogger(__name__)

# $ per 1M tokens: input, cached input, output (same table as design3d/llm.py, 2026-10-28).
PRICES = {
    "gpt-6.1-terra": (Decimal("1.00"), Decimal("0.05"), Decimal("5.00")),
    "gpt-6.1-sol": (Decimal("2.00"), Decimal("0.10"), Decimal("10.00")),
    "gpt-6-luna": (Decimal("0.10"), Decimal("0.01"), Decimal("0.50")),
}
DEFAULT_PRICE = PRICES["gpt-6.1-sol"]  # an unknown model is priced high, never free


class AiError(Exception):
    """The model could not be reached or answered something unusable. The
    chat turns this into "nothing was published" (REQ-G.56). A call that was
    made and answered nonsense still cost money, so the error carries its
    tokens and the chat records them."""

    def __init__(self, message, tokens_in=0, tokens_out=0, model_name=""):
        super().__init__(message)
        self.tokens_in, self.tokens_out, self.model_name = tokens_in, tokens_out, model_name


def model():
    return getattr(settings, "GALLERY_MODEL", "gpt-6.1-terra")


def stub_mode():
    return not (getattr(settings, "OPENAI_API_KEY", "") or "")


def cost(model_name, tokens_in, tokens_out, tokens_cached=0):
    pin, pcache, pout = PRICES.get(model_name, DEFAULT_PRICE)
    return ((Decimal(tokens_in - tokens_cached) * pin + Decimal(tokens_cached) * pcache
             + Decimal(tokens_out) * pout) / Decimal(1_000_000)).quantize(Decimal("0.0001"))


def estimate(text, max_out):
    """A ceiling for a call before it is made: three characters a token is
    generous for English and code, and Hebrew runs fewer characters a token."""
    tokens_in = len(text) // 3 + 200
    return cost(model(), tokens_in, max_out)


def parse(text):
    """The JSON object in a reply, fences and all. AiError when there is none."""
    text = (text or "").strip()
    fenced = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.S)
    if fenced:
        text = fenced.group(1)
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        raise AiError("no JSON in the answer")
    try:
        value = json.loads(text[start:end + 1])
    except json.JSONDecodeError as exc:
        raise AiError(f"bad JSON: {exc}") from None
    if not isinstance(value, dict):
        raise AiError("the answer is not an object")
    return value


_client = None


def _openai():
    global _client
    if _client is None:
        from openai import OpenAI

        _client = OpenAI(api_key=settings.OPENAI_API_KEY, timeout=90)
    return _client


def ask(system, user, max_out=1500, stub=None):
    """One call. Returns (parsed JSON, tokens_in, tokens_out, model name).
    `stub` is what to answer without a key (a dict)."""
    if stub_mode():
        return dict(stub or {}), 0, 0, "stub"
    name = model()
    try:
        r = _openai().responses.create(model=name, instructions=system, input=user, max_output_tokens=max_out)
    except Exception as exc:  # network, timeout, quota: all mean "no answer"
        log.warning("gallery llm: %s", exc)
        raise AiError(str(exc)[:200]) from None
    u = r.usage
    try:
        return parse(r.output_text or ""), u.input_tokens, u.output_tokens, name
    except AiError as exc:
        raise AiError(str(exc), u.input_tokens, u.output_tokens, name) from None
