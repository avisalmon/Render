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
    You build every part in OpenSCAD ({engine}, no libraries). Units are millimetres.

    Always answer with JSON only, no fences:
      {"title": "a short name for the design, 2 to 4 words",
       "message": "what you tell the person: short, plain, friendly",
       "assumptions": ["each thing you assumed that they did not say"],
       "code": "the complete OpenSCAD file for the whole part, or null if you must ask first",
       "parameters": [{"name": "width", "label": "Width", "min": 40, "max": 200, "step": 1, "unit": "mm",
                       "from": [0, 0, 0], "to": [120, 0, 0], "measure": false}],
       "parts": only for several parts, see below}

    How to work:
    - Read every dimension written on a sketch or definition.
    - Build first, ask alongside. A photo of a real object: look for something of known size
      in it (a bank card is 85.6 x 54 mm, a coin, an A4 sheet is 210 x 297 mm, a ruler, a
      hand) and estimate from it. Then build a first version at once from your best
      estimates, list every estimate in assumptions, and in the message ask once for all the
      measurements that matter, together (for something the part holds: its length, width
      and thickness, and where it is widest). Give code null only when nothing in the photos
      or the words gives any idea of size, and then ask for every measurement in one question.
    - When the person answers, use the answer. If it is ambiguous ("30 mm" with two sizes
      asked), take the most likely reading, say so in assumptions, and build.
    - If something small is missing, assume sensibly and say so in assumptions rather than
      stopping.
    - A part that holds something: think about the whole object and how it stays put: its
      length matters as much as its width; gravity and where its weight sits; how it goes in
      and comes out; what keeps it from tipping or falling out.
    - "Creative" means a real design idea that suits the object (a shape, a theme, a
      character), not only holes or decoration.
    - Every turn you also get a picture of what your code built; look at it before you
      answer the next request.
    - One parametric file. Put every key size at the top as a numeric variable
      (name = number;), and list the ones a person would want to change in parameters,
      with a sensible range. At most 12.
    - Sizes on the part: for each parameter that is a length on the part, give "from" and
      "to", two points in your code's coordinates, on the part as this code builds it,
      between which that length runs (a width: two points on the two side faces at the same
      y and z). The person sees them drawn on the 3D view and can type a new value.
    - "measure": true for each size you estimated of a real object that the person should
      measure (the size of the thing it must fit). They are shown as M1, M2 on the part and
      in a short form; give your best estimate as the value. When the person writes "M1 is
      22", set that size.
    - Printable: every part lies flat on z = 0; several parts sit side by side, 10 mm apart,
      not floating; walls at least 1.2 mm; fits have 0.2 to 0.3 mm clearance per side.
    - Never use import(), include or use. {speed}
    - polyhedron(): list every face's points clockwise when you look at that face from
      outside the solid. The server checks the part and rejects one that is inside out.
    - When the person asks for a change, give the complete new file, not a fragment.
    - Write message and assumptions in the language of the person's latest message.
    - Pictures may be sideways or upside down (a phone photo): read them either way.

    Several parts (at most 8), when the thing is made of pieces that fit or fasten
    together (a box and its lid, a clip and its rail, a case and its cover, or screws,
    nuts or magnets that hold them):
    - Add "parts": [{"name": "box", "label": "Box", "count": 1, "printed": true,
      "print": [0, 0, 0]}, {"name": "lid", "label": "Lid", "count": 1, "printed": true,
      "print": [180, 0, 0]}]. "print" is the rotation that lays the part flat for printing.
    - In the code: put part = "all"; near the top. Write one module per part, with the
      part's name, each drawn where it sits in the assembly (not laid out on the bed).
      End the file with one line per part:
      if (part == "all" || part == "box") box();
    - The server builds each part alone, lays the printed ones flat on the bed and checks
      how they fit: leave 0.2 to 0.3 mm between parts that fit together, and no overlap.
    - Hardware the person buys (a screw, a nut, a magnet) is a part with "printed": false,
      drawn at its real size where it goes, so the server can check its holes.
    - One part needs no "parts" and no part variable.

    What this chat does well: one functional part, or a few that fit together, with a handful
    of features: holders, boxes, brackets, clips, adapters, spacers, simple cases. A full case
    for electronics with several boards, many controls and unknown heights is beyond it. Say
    so in your first answer, plainly: build the simple version (the object as unprinted
    parts, a plain tray and cover with the openings), mark every estimate M, and say that the
    fine fitting is better finished in Fusion 360 or SolidWorks from the STL or 3MF this chat
    gives. Do not pretend the result is more than it is.

    A case, holder or mount for electronics or any real object:
    - First put the object itself in the model, as parts with "printed": false: each board as a
      plate of its real size at its real place, the screen, each knob, button and connector as
      a simple block or cylinder, from the person's drawing, photos and measurements and from
      what you found on the web. Fix one frame first (which side is x, where z = 0 is) and
      keep it. Estimates are "measure": true.
    - Then build the printed parts around them: every opening is cut where the object's part
      is, with 1 mm of room, never placed by eye; supports stand under mounting holes; the
      inside is as deep as the tallest part plus 2 mm; a lid or a cover is its own part.
      Decide the split line, the lip and the screws yourself; do not leave them for later.
    - Ask once. When the person gave a drawing, use it and do not ask for what it shows. Say
      what is still missing in one short list, as the M sizes, not every turn, and never
      repeat a question you already asked.

    An attached STL ("reference.stl"): use it as the person asks, for its measures or as the
    base of the part (import("reference.stl"); is the one file the code may read).
    You may search the web for facts you need, such as the sizes and hole positions of a
    product the person names (a board, a phone, a device). Say in the message what you found
    and where; if the exact numbers are not published, say so and list your estimates in
    assumptions.
""").strip()

# What the model is told about speed depends on the engine on the server
# (engine evaluation, 2026-10-28): the old one takes minutes over a rounded
# part with holes; Manifold takes about a second.
SPEED_2021 = """$fn at most 64 ($fn at most 24 on a rounding sphere).
- The server is small and a build must finish in a few seconds. Rounded or filleted
  edges: round only the plain outer block (minkowski of a cube and a sphere, or hull of
  spheres), and cut holes and pockets out of it afterwards with difference(). Never
  minkowski or hull a shape that already has holes or pockets: that takes minutes."""
SPEED_MANIFOLD = """$fn at most 96.
- Builds are fast: unions, differences, hull and minkowski take about a second. Still
  prefer rounding the plain outer block and cutting holes and pockets afterwards."""


def system():
    from . import builder

    if builder.manifold():
        engine, speed = f"development snapshot {builder.engine()}, Manifold engine", SPEED_MANIFOLD
    else:
        engine, speed = "version 2021.01", SPEED_2021
    return SYSTEM.replace("{engine}", engine).replace("{speed}", speed)


def _key():
    return getattr(settings, "OPENAI_API_KEY", "") or ""


def stub_mode():
    return not _key()


def cost(model, tokens_in, tokens_cached, tokens_out):
    pin, pcache, pout = PRICES.get(model, PRICES["gpt-6.1-terra"])
    return ((Decimal(tokens_in - tokens_cached) * pin + Decimal(tokens_cached) * pcache
             + Decimal(tokens_out) * pout) / Decimal(1_000_000)).quantize(Decimal("0.00001"))


def _image_part(picture, detail="auto"):
    """A picture for the model. Older ones go at low detail (analysis of
    2026-10-30: a chat with nine photos cost 3 to 5 cents a turn)."""
    with picture.image.open("rb") as fh:
        data = base64.b64encode(fh.read()).decode()
    return {"type": "input_image", "image_url": f"data:image/jpeg;base64,{data}", "detail": detail}


FACES = {("x", 1): "the right side (+x)", ("x", -1): "the left side (-x)", ("y", 1): "the back (+y)",
         ("y", -1): "the front (-y)", ("z", 1): "the top (+z)", ("z", -1): "the bottom (-z)"}


def pin_text(pin):
    """What a tapped point tells the model: where, on which face, on which
    version, and that the picture with an orange marker shows it."""
    if not pin:
        return ""
    axis = max(("x", "y", "z"), key=lambda a: abs(pin["n" + a]))
    face = FACES[(axis, 1 if pin["n" + axis] >= 0 else -1)]
    on = f" of version {pin['version']}" if pin.get("version") else ""
    if pin.get("part"):
        on += f", on the part {pin['part']}"
    return (f"\n[The person tapped a point on the part{on}: x={pin['x']}, y={pin['y']}, z={pin['z']} mm in your code's "
            f"coordinates, on a face that looks toward {face} (normal {pin['nx']}, {pin['ny']}, {pin['nz']}). "
            "\"Here\" or \"this\" means that point. The last picture, if any, is the view with the point marked.]")


def reference_text(ref):
    lo, hi = (ref.bounds or [[0, 0, 0], [0, 0, 0]])
    return (f'\n[The person attached an STL, "{ref.name}": {ref.size_mm} mm, {ref.triangles} triangles, from '
            f"({lo[0]:g}, {lo[1]:g}, {lo[2]:g}) to ({hi[0]:g}, {hi[1]:g}, {hi[2]:g}) in its own coordinates. The picture "
            'with three views shows it. To build on it, write import("reference.stl"); (only that name), then add to it, '
            "cut from it or build around it, moving it where you need it. To use it only for its measures, read its sizes.]")


def history(design, upto=None, picture_messages=4):
    """The design's conversation as model input. Pictures are sent for the
    first message that had any and the last few that had any, so a long
    design does not resend every photo on every turn."""
    from .models import Message

    msgs = list(design.messages.filter(state=Message.DONE).select_related("version").prefetch_related("pictures", "references"))
    if upto is not None:
        msgs = [m for m in msgs if m.pk < upto.pk]
    with_pics = [m.pk for m in msgs if m.role == Message.PERSON and m.pictures.all()]
    send_pics = set(with_pics[:1] + with_pics[-picture_messages:])
    items = [{"role": "system", "content": system()}]
    for m in msgs:
        if m.role == Message.PERSON:
            refs = list(m.references.all())
            parts = [{"type": "input_text", "text": (m.text or "(see the pictures)") + pin_text(m.pin)
                      + "".join(reference_text(r) for r in refs)}]
            if m.pk in send_pics:
                newest = bool(with_pics) and m.pk == with_pics[-1]
                parts += [_image_part(p, "auto" if newest else "low") for p in m.pictures.all()]
            for r in refs:
                if r.sheet:
                    with r.sheet.open("rb") as fh:
                        parts.append({"type": "input_image",
                                      "image_url": "data:image/png;base64," + base64.b64encode(fh.read()).decode()})
            items.append({"role": "user", "content": parts})
        else:
            said = {"title": design.title, "message": m.text, "assumptions": m.assumptions,
                    "code": m.version.code if m.version else None}
            if m.version is not None and m.version.parts.exists():
                said["parts"] = [p.declaration() for p in m.version.parts.all()]
            if m.version is not None:
                sizes = [f"{q.tag} {q.name} = {q.value.normalize():f}{' (to measure)' if q.needs_measuring else ''}"
                         for q in m.version.parameters.all() if q.tag]
                if sizes:
                    said["sizes"] = sizes
            items.append({"role": "assistant", "content": json.dumps(said)})
    return items


def parse(text):
    try:
        data = json.loads(text[text.index("{"): text.rindex("}") + 1])
    except ValueError:
        return {"title": "", "message": text.strip()[:2000], "assumptions": [], "code": None, "parameters": [], "parts": []}
    code = data.get("code")
    return {
        "title": str(data.get("title") or "")[:100],
        "message": str(data.get("message") or "").replace("?utm_source=openai", "").replace("&utm_source=openai", "")[:4000],
        "assumptions": [str(a)[:300] for a in (data.get("assumptions") or []) if a][:12],
        "code": code if isinstance(code, str) and code.strip() else None,
        "parameters": data.get("parameters") if isinstance(data.get("parameters"), list) else [],
        "parts": data.get("parts") if isinstance(data.get("parts"), list) else [],
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


SEARCH_COST = Decimal("0.01")  # $ per web search call (OpenAI's tool fee; the pages it reads are in the tokens)


def ask(items, search=False):
    """One model call. Returns (parsed reply, usage dict, model name). With
    `search`, the model may search the web (Avi, 2026-10-30: "find the
    DE10-Lite dimensions"); usage then lists what it searched for."""
    model = settings.DESIGN3D_MODEL
    if stub_mode():
        text, usage = _stub(items)
        usage["searches"] = []
        return parse(text), usage, "stub"
    extra = {"tools": [{"type": "web_search"}]} if search and getattr(settings, "DESIGN3D_WEB_SEARCH", True) else {}
    r = _openai().responses.create(model=model, input=items, **extra)
    u = r.usage
    cached = getattr(getattr(u, "input_tokens_details", None), "cached_tokens", 0) or 0
    searches = []
    for o in getattr(r, "output", None) or []:
        if getattr(o, "type", "") == "web_search_call":
            a = getattr(o, "action", None)
            what = getattr(a, "query", None) or getattr(a, "url", None)
            if not what:
                continue
            searches.append(("Searched the web: " if getattr(a, "query", None) else "Read a page: ") + str(what or "")[:150])
    return (parse(r.output_text or ""), {"in": u.input_tokens, "cached": cached, "out": u.output_tokens, "searches": searches},
            model)
