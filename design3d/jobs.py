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

from . import builder, llm, params, render
from .models import Design, Message, Parameter, Version

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


def make_version(design, code, parent, made_by, proposed=None, from_values=None):
    """Build `code` into the next version of the design. Returns the
    version, ready or failed; parameters come from the chat's proposal, or
    are carried over from the parent with the slider values."""
    with transaction.atomic():
        number = (design.versions.aggregate(m=Max("number"))["m"] or 0) + 1
        v = Version.objects.create(design=design, number=number, parent=parent, made_by=made_by, code=code)
    try:
        stl, took = builder.build(code)
    except builder.BuildError as exc:
        v.status, v.error = Version.FAILED, str(exc)[:4000]
        v.save(update_fields=["status", "error"])
        return v
    tris = render.read_stl(stl)
    v.size_mm = render.size_mm(tris)
    v.build_seconds = Decimal(str(round(took, 1)))
    v.stl.save(f"v{number}.stl", ContentFile(stl), save=False)
    v.preview.save(f"v{number}.png", ContentFile(render.preview(stl)), save=False)
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


def _turn(msg, design):
    items = llm.history(design, upto=msg)
    reply, usage, model = llm.ask(items)
    _add_usage(msg, usage, model)
    had_ready = design.versions.filter(status=Version.READY).exists()
    version = None

    if reply["code"]:
        msg.state = Message.BUILDING
        msg.save(update_fields=["state", "model", "tokens_in", "tokens_cached", "tokens_out", "cost_usd"])
        version = make_version(design, reply["code"], design.current, Version.CHAT, reply["parameters"])
        tries = 0
        while version.status == Version.FAILED and tries < REPAIRS:
            tries += 1
            items = items + [{"role": "assistant", "content": _as_json(reply)},
                             {"role": "user", "content": [{"type": "input_text", "text":
                                 f"The OpenSCAD build failed:\n{version.error}\nFix it and answer in the same JSON."}]}]
            fixed, usage, model = llm.ask(items)
            _add_usage(msg, usage, model)
            if not fixed["code"]:
                break
            reply = {**reply, **{k: v for k, v in fixed.items() if v}}
            version = make_version(design, fixed["code"], design.current, Version.CHAT, fixed["parameters"] or reply["parameters"])

        if version.status == Version.READY and not had_ready and not llm.stub_mode():
            version, reply = _self_check(msg, design, items, reply, version)

    msg.text = reply["message"] or ("Here it is." if version else "")
    if version is not None and version.status == Version.FAILED:
        msg.text += "\n\nI could not build it this time. Tell me what to change, or ask me to try again."
    msg.assumptions = reply["assumptions"]
    msg.version = version
    msg.state = Message.DONE
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


def _self_check(msg, design, items, reply, version):
    """Show the model what it built, once, and let it correct itself."""
    import base64

    with version.stl.open("rb") as fh:
        sheet = render.sheet(fh.read())
    items = items + [
        {"role": "assistant", "content": _as_json(reply)},
        {"role": "user", "content": [
            {"type": "input_text", "text": f"This is what your code built (size {version.size_mm} mm). Compare it with "
                                           "what I asked and my pictures. If it is right, answer with code null and a short "
                                           "message for me; if not, give the corrected full code."},
            {"type": "input_image", "image_url": "data:image/png;base64," + base64.b64encode(sheet).decode()}]}]
    checked, usage, model = llm.ask(items)
    _add_usage(msg, usage, model)
    if not checked["code"]:
        return version, reply
    better = make_version(design, checked["code"], version, Version.CHAT, checked["parameters"] or reply["parameters"])
    if better.status != Version.READY:
        return version, reply
    return better, {**reply, **{k: v for k, v in checked.items() if v and k != "message"},
                    "message": reply["message"] + "\n\n" + (checked["message"] or "I checked it and corrected it.")}
