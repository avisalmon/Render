"""The conversation with the model (REQ-D3.12, D3.13, D3.15).

The model never writes an STL: it answers JSON with a message, the
assumptions it made, and the whole part as OpenSCAD code (or no code, when
it must ask first). The prompt is the one measured in the sketch-to-stl
skill, with the questions about photos of real objects added.

Without an OpenAI key (a developer's PC, tests) the stub answers with a
fixed part, so every screen can be built and tested without a bill.
"""

import base64
import json
import logging
import textwrap
from decimal import Decimal

from django.conf import settings

log = logging.getLogger(__name__)

# $ per 1M tokens: input, cached input, output (developers.openai.com/api/docs/pricing, 2026-10-28).
PRICES = {
    "gpt-6.1-terra": (Decimal("1.00"), Decimal("0.05"), Decimal("5.00")),
    "gpt-6.1-sol": (Decimal("2.00"), Decimal("0.10"), Decimal("10.00")),
    "gpt-6-luna": (Decimal("0.10"), Decimal("0.01"), Decimal("0.50")),
}

SYSTEM = textwrap.dedent("""
    You are design3d, a friendly CAD partner. A person shows you what they want to make,
    in words, with a drawing or hand sketch, a written definition, or a photo of a real
    object, and you talk with them until it is right; then they keep asking for changes.
    You build every part in OpenSCAD (version 2021.01, no libraries). Units are millimetres.

    Always answer with JSON only, no fences:
      {"title": "a short name for the design, 2 to 4 words",
       "message": "what you tell the person: short, plain, friendly",
       "assumptions": ["each thing you assumed that they did not say"],
       "code": "the complete OpenSCAD file for the whole part, or null if you must ask first",
       "parameters": [{"name": "wall", "label": "Wall thickness", "min": 1, "max": 5, "step": 0.5, "unit": "mm"}]}

    How to work:
    - Read every dimension written on a sketch or definition.
    - A photo of a real object has no scale. Do not guess the size of the object the part
      must fit: ask for the one or two measurements that matter (with code null), and
      suggest putting a coin or a card next to the object in the next photo.
    - Otherwise, if something small is missing, assume sensibly and say so in assumptions
      rather than stopping.
    - One parametric file. Put every key size at the top as a numeric variable
      (name = number;), and list the ones a person would want to change in parameters,
      with a sensible range. At most 8.
    - Printable: every part lies flat on z = 0; several parts sit side by side, 10 mm apart,
      not floating; walls at least 1.2 mm; fits have 0.2 to 0.3 mm clearance per side.
    - Never use import(), include or use. $fn at most 64 ($fn at most 24 on a rounding sphere).
    - The server is small and a build must finish in a few seconds. Rounded or filleted
      edges: round only the plain outer block (minkowski of a cube and a sphere, or hull of
      spheres), and cut holes and pockets out of it afterwards with difference(). Never
      minkowski or hull a shape that already has holes or pockets: that takes minutes.
    - When the person asks for a change, give the complete new file, not a fragment.
""").strip()


def _key():
    return getattr(settings, "OPENAI_API_KEY", "") or ""


def stub_mode():
    return not _key()


def cost(model, tokens_in, tokens_cached, tokens_out):
    pin, pcache, pout = PRICES.get(model, PRICES["gpt-6.1-terra"])
    return ((Decimal(tokens_in - tokens_cached) * pin + Decimal(tokens_cached) * pcache
             + Decimal(tokens_out) * pout) / Decimal(1_000_000)).quantize(Decimal("0.00001"))


def _image_part(picture):
    with picture.image.open("rb") as fh:
        data = base64.b64encode(fh.read()).decode()
    return {"type": "input_image", "image_url": f"data:image/jpeg;base64,{data}"}


def history(design, upto=None, picture_messages=4):
    """The design's conversation as model input. Pictures are sent for the
    first message that had any and the last few that had any, so a long
    design does not resend every photo on every turn."""
    from .models import Message

    msgs = list(design.messages.filter(state=Message.DONE).select_related("version").prefetch_related("pictures"))
    if upto is not None:
        msgs = [m for m in msgs if m.pk < upto.pk]
    with_pics = [m.pk for m in msgs if m.role == Message.PERSON and m.pictures.all()]
    send_pics = set(with_pics[:1] + with_pics[-picture_messages:])
    items = [{"role": "system", "content": SYSTEM}]
    for m in msgs:
        if m.role == Message.PERSON:
            parts = [{"type": "input_text", "text": m.text or "(see the pictures)"}]
            if m.pk in send_pics:
                parts += [_image_part(p) for p in m.pictures.all()]
            items.append({"role": "user", "content": parts})
        else:
            items.append({"role": "assistant", "content": json.dumps({
                "title": design.title, "message": m.text, "assumptions": m.assumptions,
                "code": m.version.code if m.version else None})})
    return items


def parse(text):
    try:
        data = json.loads(text[text.index("{"): text.rindex("}") + 1])
    except ValueError:
        return {"title": "", "message": text.strip()[:2000], "assumptions": [], "code": None, "parameters": []}
    code = data.get("code")
    return {
        "title": str(data.get("title") or "")[:100],
        "message": str(data.get("message") or "")[:4000],
        "assumptions": [str(a)[:300] for a in (data.get("assumptions") or []) if a][:12],
        "code": code if isinstance(code, str) and code.strip() else None,
        "parameters": data.get("parameters") if isinstance(data.get("parameters"), list) else [],
    }


STUB_CODE = textwrap.dedent("""
    // A pencil holder (design3d stub mode: no OpenAI key on this server)
    diameter = 70;
    height = 90;
    wall = 2;
    hole = 8.6;
    holes = 3;
    $fn = 48;
    difference() {
        cylinder(d = diameter, h = height);
        translate([0, 0, wall]) cylinder(d = diameter - 2 * wall, h = height);
    }
""").strip()


def _stub(items):
    asked = items[-1]["content"] if items else ""
    text = asked[0]["text"] if isinstance(asked, list) and asked else str(asked)
    return json.dumps({
        "title": "Pencil holder",
        "message": "Stub mode, no model on this server: here is a sample part. " + text[:80],
        "assumptions": ["This is a fixed sample, not your design."],
        "code": STUB_CODE,
        "parameters": [{"name": "diameter", "label": "Diameter", "min": 40, "max": 120, "step": 1, "unit": "mm"},
                       {"name": "height", "label": "Height", "min": 30, "max": 150, "step": 1, "unit": "mm"},
                       {"name": "wall", "label": "Wall", "min": 1.2, "max": 5, "step": 0.2, "unit": "mm"}],
    }), {"in": 0, "cached": 0, "out": 0}


_client = None


def _openai():
    global _client
    if _client is None:
        from openai import OpenAI

        _client = OpenAI(api_key=_key(), timeout=120)
    return _client


def ask(items):
    """One model call. Returns (parsed reply, usage dict, model name)."""
    model = settings.DESIGN3D_MODEL
    if stub_mode():
        text, usage = _stub(items)
        return parse(text), usage, "stub"
    r = _openai().responses.create(model=model, input=items)
    u = r.usage
    cached = getattr(getattr(u, "input_tokens_details", None), "cached_tokens", 0) or 0
    return parse(r.output_text or ""), {"in": u.input_tokens, "cached": cached, "out": u.output_tokens}, model
