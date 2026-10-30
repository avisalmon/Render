"""A chat turn, run in the background (REQ-D3.12, D3.20 to D3.22).

The web request only records the person's message and an empty assistant
message in the `thinking` state, starts a thread, and returns; the page
polls the message's state. A build never runs inside a web request
(REQ-D3.43). In tests (`DESIGN3D_SYNC`) the turn runs inline.

A turn that dies with the process (a deploy restarts it) is found by
`heal()` on the person's next visit and ends as `failed`, with a line that
says to send it again (methodology 22).
"""

import logging
import threading
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.core.files.base import ContentFile
from django.db import close_old_connections, transaction
from django.db.models import Max, Sum
from django.utils import timezone

from . import builder, llm, params, parts, printcheck, render
from .models import Design, Message, Parameter, Part, Version

log = logging.getLogger(__name__)

REPAIRS = 3
STUCK_AFTER = timedelta(minutes=10)


def spent_today(maker):
    start = timezone.localtime().replace(hour=0, minute=0, second=0, microsecond=0)
    total = Message.objects.filter(design__owner=maker, created_at__gte=start).aggregate(s=Sum("cost_usd"))["s"]
    return total or Decimal("0")


def over_limit(maker):
    limit = maker.limit
    return limit is not None and spent_today(maker) >= limit


def heal(design):
    """Turns stuck in thinking/building for too long end as failed."""
    old = timezone.now() - STUCK_AFTER
    design.messages.filter(state__in=[Message.THINKING, Message.BUILDING], created_at__lt=old).update(
        state=Message.FAILED, text="This turn was interrupted. Please send it again.")
    design.versions.filter(status=Version.BUILDING, created_at__lt=old).update(
        status=Version.FAILED, error="This build was interrupted. Please try again.")


def start(assistant):
    if getattr(settings, "DESIGN3D_SYNC", False):
        run(assistant.pk)
        return
    threading.Thread(target=_thread, args=(assistant.pk,), daemon=True, name=f"design3d-turn-{assistant.pk}").start()


def start_sliders(design, base, code, values):
    """A slider build in the background; the page polls the version."""
    def work():
        try:
            v = make_version(design, code, base, Version.SLIDERS, from_values=values)
            if v.status == Version.READY:
                Design.objects.filter(pk=design.pk).update(current=v, updated_at=timezone.now())
        except Exception:
            log.exception("design3d: slider build for design %s failed", design.pk)
            Version.objects.filter(design=design, status=Version.BUILDING).update(
                status=Version.FAILED, error="Something went wrong on our side.")
        finally:
            if not getattr(settings, "DESIGN3D_SYNC", False):
                close_old_connections()

    if getattr(settings, "DESIGN3D_SYNC", False):
        work()
    else:
        threading.Thread(target=work, daemon=True, name=f"design3d-sliders-{design.pk}").start()


def _thread(pk):
    try:
        run(pk)
    finally:
        close_old_connections()


def _add_usage(msg, usage, model):
    msg.model = model
    msg.tokens_in += usage["in"]
    msg.tokens_cached += usage["cached"]
    msg.tokens_out += usage["out"]
    msg.cost_usd += llm.cost(model if model in llm.PRICES else settings.DESIGN3D_MODEL,
                             usage["in"], usage["cached"], usage["out"]) if model != "stub" else Decimal("0")


def run_checks(stl):
    """The print-ready findings, or None if the check itself broke: a check
    never stops a part from being shown."""
    try:
        return printcheck.check(stl)
    except Exception:
        log.exception("design3d: print check failed")
        return None


def checks_for(version):
    """A ready version's findings, checking an older version on first look."""
    if version is not None and version.status == Version.READY and version.checks is None and version.stl:
        with version.stl.open("rb") as fh:
            version.checks = run_checks(fh.read())
        if version.checks is not None:
            Version.objects.filter(pk=version.pk).update(checks=version.checks)
    return version


def view_stl(version):
    """The part as people see it: for several parts, all of them in their
    assembled places (the version's own STL is then the print plate)."""
    if version.parts.exists():
        stls = []
        for p in version.parts.all():
            with p.stl.open("rb") as fh:
                stls.append(fh.read())
        return parts.assembled(stls)
    with version.stl.open("rb") as fh:
        return fh.read()


def _build_parts(v, code, declared):
    """Chapter 7: each part alone, then flat, on the plate, the 3MF and the
    fit. Returns seconds of building; raises BuildError."""
    built, took = [], 0.0
    for d in declared:
        empty = builder.BuildError(f'The part "{d["name"]}" came out empty. Draw it when part == "{d["name"]}": '
                                   f'end the file with if (part == "all" || part == "{d["name"]}") {d["name"]}();')
        try:
            stl, seconds = builder.build(code, part=d["name"])
        except builder.BuildError as exc:
            if "empty" in str(exc).lower():
                raise empty from exc
            raise builder.BuildError(f'Building the part "{d["name"]}": {exc}') from exc
        took += seconds
        tris = render.read_stl(stl)
        if not tris:
            raise empty
        built.append((d, stl, tris))
    pieces = []
    for i, (d, stl, tris) in enumerate(built):
        p = Part(version=v, name=d["name"], label=d["label"], position=i, count=d["count"], printed=d["printed"],
                 color=parts.COLORS[i % len(parts.COLORS)], size_mm=render.size_mm(tris))
        p.stl.save(f"{d['name']}.stl", ContentFile(stl), save=False)
        if d["printed"]:
            flat, how = parts.orient(tris, d["print"])
            p.orientation = how
            flat_stl = parts.to_stl(flat)
            p.print_stl.save(f"{d['name']}-print.stl", ContentFile(flat_stl), save=False)
            p.checks = run_checks(flat_stl)
            for c in range(d["count"]):
                pieces.append((d["label"] + (f" {c + 1}" if d["count"] > 1 else ""), flat))
        p.save()
    if not pieces:
        raise builder.BuildError("No part is printed. At least one part needs \"printed\": true.")
    laid = parts.plate(pieces)
    plate_stl = parts.to_stl([t for _, tris in laid for t in tris])
    v.stl.save(f"v{v.number}.stl", ContentFile(plate_stl), save=False)
    v.file_3mf.save(f"v{v.number}.3mf", ContentFile(parts.to_3mf(laid)), save=False)
    v.checks = run_checks(plate_stl)
    try:
        v.fit = parts.fit([(d["name"], d["label"], d["printed"], tris) for d, _, tris in built])
    except Exception:
        log.exception("design3d: fit check failed for version %s", v.pk)
        v.fit = None
    together = parts.assembled([stl for _, stl, _ in built])
    v.size_mm = render.size_mm(render.read_stl(together))
    v.preview.save(f"v{v.number}.png", ContentFile(render.preview(together)), save=False)
    return took


def _copy_file(src, dst, name):
    if src:
        with src.open("rb") as fh:
            dst.save(name, ContentFile(fh.read()), save=False)


def copy_design(source, maker):
    """A shared design's current part as the first version of a new design
    of `maker` (Avi, 2026-10-29). The part, its sizes and its parts come
    along; the chat and the pictures stay with their owner (REQ-D3.30)."""
    src = source.current
    with transaction.atomic():
        d = Design.objects.create(owner=maker, title=f"{source.title} (copy)"[:100], copied_from=source)
        v = Version(design=d, number=1, made_by=Version.COPY, code=src.code, status=Version.READY,
                    size_mm=src.size_mm, build_seconds=src.build_seconds, checks=src.checks, fit=src.fit)
        _copy_file(src.stl, v.stl, "v1.stl")
        _copy_file(src.preview, v.preview, "v1.png")
        _copy_file(src.file_3mf, v.file_3mf, "v1.3mf")
        v.save()
        for p in src.parameters.all():
            Parameter.objects.create(version=v, name=p.name, label=p.label, value=p.value, minimum=p.minimum,
                                     maximum=p.maximum, step=p.step, unit=p.unit, position=p.position)
        for p in src.parts.all():
            q = Part(version=v, name=p.name, label=p.label, position=p.position, count=p.count, printed=p.printed,
                     orientation=p.orientation, size_mm=p.size_mm, checks=p.checks, color=p.color)
            _copy_file(p.stl, q.stl, f"{p.name}.stl")
            _copy_file(p.print_stl, q.print_stl, f"{p.name}-print.stl")
            q.save()
        Message.objects.create(
            design=d, role=Message.ASSISTANT, state=Message.DONE, version=v,
            text=f"This is a copy of \u201c{source.title}\u201d by {source.owner.display_name}. It is yours now: "
                 "tell me what to change, or move the sizes.")
        d.current = v
        d.save(update_fields=["current"])
    return d


def make_version(design, code, parent, made_by, proposed=None, from_values=None, declared=None):
    """Build `code` into the next version of the design. Returns the
    version, ready or failed; parameters come from the chat's proposal, or
    are carried over from the parent with the slider values. `declared` is
    the chat's part list (Chapter 7); slider builds keep the parent's."""
    if from_values is not None and parent is not None:
        declared = [p.declaration() for p in parent.parts.all()]
    declared = parts.clean(declared or [])
    with transaction.atomic():
        number = (design.versions.aggregate(m=Max("number"))["m"] or 0) + 1
        v = Version.objects.create(design=design, number=number, parent=parent, made_by=made_by, code=code)
    try:
        if declared:
            took = _build_parts(v, code, declared)
        else:
            stl, took = builder.build(code)
    except builder.BuildError as exc:
        v.parts.all().delete()
        v.status, v.error = Version.FAILED, str(exc)[:4000]
        v.save(update_fields=["status", "error"])
        return v
    if not declared:
        tris = render.read_stl(stl)
        v.size_mm = render.size_mm(tris)
        v.stl.save(f"v{number}.stl", ContentFile(stl), save=False)
        v.preview.save(f"v{number}.png", ContentFile(render.preview(stl)), save=False)
        v.checks = run_checks(stl)
    v.build_seconds = Decimal(str(round(took, 1)))
    v.status = Version.READY
    v.save()
    if from_values is not None and parent is not None:
        for p in parent.parameters.all():
            Parameter.objects.create(version=v, name=p.name, label=p.label, value=params.value_in(code, p.name) or p.value,
                                     minimum=p.minimum, maximum=p.maximum, step=p.step, unit=p.unit, position=p.position)
    else:
        for p in params.clean(proposed, code):
            Parameter.objects.create(version=v, **p)
    return v


def run(pk):
    msg = Message.objects.select_related("design", "design__owner").get(pk=pk)
    design = msg.design
    try:
        _turn(msg, design)
    except Exception:
        log.exception("design3d: turn %s failed", pk)
        Message.objects.filter(pk=pk).update(state=Message.FAILED,
                                             text="Something went wrong on our side. Please send it again.")


def _note(msg, text):
    """A line in the turn's trail, so the person can look inside a long
    turn and see it is moving (Avi, 2026-10-28)."""
    seconds = int((timezone.now() - msg.created_at).total_seconds())
    msg.trail = (msg.trail or []) + [[seconds, text[:200]]]
    Message.objects.filter(pk=msg.pk).update(trail=msg.trail)


def _built(msg, version):
    if version.status == Version.READY:
        _note(msg, f"Version {version.number} built in {version.build_seconds} s")
    else:
        _note(msg, f"Version {version.number} did not build: {version.error.splitlines()[0] if version.error else 'no part'}")


def _step(msg, text, state=None):
    """What the turn is doing now, for the page (REQ-D3.12)."""
    _note(msg, text)
    msg.step = text
    fields = {"step": text}
    if state:
        msg.state = state
        fields["state"] = state
    Message.objects.filter(pk=msg.pk).update(**fields)


def _show(design, version):
    """A ready version goes on screen at once, before the turn ends."""
    if version.status == Version.READY:
        design.current = version
        Design.objects.filter(pk=design.pk).update(current=version, updated_at=timezone.now())


def _turn(msg, design):
    items = llm.history(design, upto=msg)
    _step(msg, "Reading your message")
    reply, usage, model = llm.ask(items)
    _add_usage(msg, usage, model)
    version = None

    if reply["code"]:
        msg.save(update_fields=["model", "tokens_in", "tokens_cached", "tokens_out", "cost_usd"])
        number = (design.versions.aggregate(m=Max("number"))["m"] or 0) + 1
        _step(msg, f"Building version {number}", Message.BUILDING)
        version = make_version(design, reply["code"], design.current, Version.CHAT, reply["parameters"],
                               declared=reply.get("parts"))
        _built(msg, version)
        _show(design, version)
        tries = 0
        while version.status == Version.FAILED and tries < REPAIRS:
            tries += 1
            _step(msg, f"Fixing a build error, try {tries} of {REPAIRS}")
            items = items + [{"role": "assistant", "content": _as_json(reply)},
                             {"role": "user", "content": [{"type": "input_text", "text":
                                 f"The OpenSCAD build failed:\n{version.error}\nFix it and answer in the same JSON."}]}]
            fixed, usage, model = llm.ask(items)
            _add_usage(msg, usage, model)
            if not fixed["code"]:
                break
            reply = {**reply, **{k: v for k, v in fixed.items() if v}}
            _note(msg, f"Building version {design.versions.aggregate(m=Max('number'))['m'] + 1}")
            version = make_version(design, fixed["code"], design.current, Version.CHAT, fixed["parameters"] or reply["parameters"],
                                   declared=fixed.get("parts") or reply.get("parts"))
            _built(msg, version)
            _show(design, version)

        # Every part the chat builds is shown back to the model once (Avi,
        # 2026-10-29: after "wall mount" and "it may fall" the chat changed the
        # part without looking at it). About half a cent a turn.
        if version.status == Version.READY and not llm.stub_mode():
            version, reply = _self_check(msg, design, items, reply, version)

    if version is not None and version.status == Version.READY:
        from . import seats

        seats.reward_friend(design.owner)  # Chapter 8: a friend's first part gives 30 turns
    msg.text = reply["message"] or ("Here it is." if version else "")
    if version is not None and version.status == Version.FAILED:
        msg.text += "\n\nI could not build it this time. Tell me what to change, or ask me to try again."
    msg.assumptions = reply["assumptions"]
    msg.version = version
    msg.state = Message.DONE
    msg.step = ""
    msg.save()
    fields = []
    if version is not None and version.status == Version.READY:
        design.current = version
        fields.append("current")
    if reply.get("title") and design.title == "New design":
        design.title = reply["title"]
        fields.append("title")
    design.save(update_fields=fields + ["updated_at"])


def _as_json(reply):
    import json

    return json.dumps({k: reply.get(k) for k in ("title", "message", "assumptions", "code")})


def _findings(version):
    warns = version.warnings
    if not warns:
        return ""
    return ("\nThe server's print check found: " + " ".join(w["fix"] for w in warns)
            + " Fix these too, unless the person asked for it that way.")


def _self_check(msg, design, items, reply, version):
    """Show the model what it built, once, and let it correct itself."""
    import base64

    sheet = render.sheet(view_stl(version))
    items = items + [
        {"role": "assistant", "content": _as_json(reply)},
        {"role": "user", "content": [
            {"type": "input_text", "text": f"This is what your code built (size {version.size_mm} mm). Compare it with "
                                           "what I asked and my pictures. If it is right, answer with code null and a short "
                                           "message for me; if not, give the corrected full code." + _findings(version)},
            {"type": "input_image", "image_url": "data:image/png;base64," + base64.b64encode(sheet).decode()}]}]
    _step(msg, "Checking the part against what you asked")
    checked, usage, model = llm.ask(items)
    _add_usage(msg, usage, model)
    if not checked["code"]:
        return version, reply
    _step(msg, "Correcting the part")
    better = make_version(design, checked["code"], version, Version.CHAT, checked["parameters"] or reply["parameters"],
                          declared=checked.get("parts") or reply.get("parts"))
    _built(msg, better)
    _show(design, better)
    if better.status != Version.READY:
        return version, reply
    return better, {**reply, **{k: v for k, v in checked.items() if v and k != "message"},
                    "message": reply["message"] + "\n\n" + (checked["message"] or "I checked it and corrected it.")}
