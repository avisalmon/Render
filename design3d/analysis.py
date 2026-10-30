"""The chats sent for analysis (Chapter 8, REQ-D3.75; Avi, 2026-10-30).

Avi's button on the People screen sends everything new since the last send,
as one zip: for every design with new messages, its whole chat (as text,
with the model, cost and steps of each turn), every version's OpenSCAD
code, the print and fit findings, and the pictures people sent. The zip goes
to Avi's two addresses, attached when it fits, and always behind a signed
link that lasts a day, because Claude reads mail through a connection that
cannot open attachments (PM-74).

People's names are kept (display names, no email addresses): the analysis is
about how the chat behaves, not about who wrote.
"""

import io
import json
import logging
import zipfile

from django.conf import settings
from django.core import signing
from django.core.files.base import ContentFile
from django.core.mail import EmailMessage
from django.db.models import Sum
from django.utils import timezone

from . import mail
from .models import Design, Export, Message, Settings

log = logging.getLogger(__name__)

TO = ["avi.salmon@gmail.com", "avisalmon@intel.com"]  # Avi's decision, 2026-10-30
MAX_ATTACH = 18 * 1024 * 1024  # bytes; Gmail takes 25 MB and base64 adds a third
SALT = "design3d-analysis"
HOURS = 24


def build(since):
    """(zip bytes, counts) for what is new since `since` (None: everything)."""
    new = Message.objects.all() if since is None else Message.objects.filter(created_at__gt=since)
    design_ids = sorted(set(new.values_list("design_id", flat=True)))
    out = io.BytesIO()
    total = new.aggregate(s=Sum("cost_usd"))["s"] or 0
    counts = {"designs": 0, "messages": new.count(), "pictures": 0, "cost_usd": f"{total:.2f}"}
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for d in Design.objects.filter(pk__in=design_ids).select_related("owner", "current"):
            counts["designs"] += 1
            root = f"design-{d.pk}"
            z.writestr(f"{root}/chat.txt", mail.chat_text(d))
            versions = []
            for v in d.versions.order_by("number").prefetch_related("parts", "parameters"):
                z.writestr(f"{root}/v{v.number}.scad", v.code)
                versions.append({"number": v.number, "made_by": v.made_by, "status": v.status, "error": v.error[:2000],
                                 "size_mm": v.size_mm, "build_seconds": str(v.build_seconds or ""),
                                 "checks": v.checks, "fit": v.fit,
                                 "parts": [p.declaration() for p in v.parts.all()],
                                 "sizes": [{"tag": q.tag, "name": q.name, "value": str(q.value), "measure": q.needs_measuring,
                                            "placed": bool(q.dim)} for q in v.parameters.all()]})
            turns = []
            for m in d.messages.prefetch_related("pictures").select_related("version"):
                pics = []
                for n, p in enumerate(m.pictures.all(), 1):
                    name = f"{root}/pictures/msg{m.pk}-{n}.jpg"
                    try:
                        with p.image.open("rb") as fh:
                            z.writestr(name, fh.read())
                        pics.append(name.split("/", 1)[1])
                        counts["pictures"] += 1
                    except OSError:
                        pics.append(f"(missing) msg{m.pk}-{n}.jpg")
                turns.append({"id": m.pk, "role": m.role, "state": m.state, "new": since is None or m.created_at > since,
                              "at": m.created_at.isoformat(), "text": m.text, "assumptions": m.assumptions,
                              "pin": m.pin, "pictures": pics, "version": m.version.number if m.version else None,
                              "model": m.model, "tokens_in": m.tokens_in, "tokens_cached": m.tokens_cached,
                              "tokens_out": m.tokens_out, "cost_usd": str(m.cost_usd), "trail": m.trail})
            z.writestr(f"{root}/design.json", json.dumps({
                "id": d.pk, "title": d.title, "owner": d.owner.display_name, "shared": d.is_shared,
                "copied_from": d.copied_from_id, "current": d.current.number if d.current else None,
                "turns": turns, "versions": versions}, indent=1, ensure_ascii=False))
        z.writestr("README.txt", (
            "design3d chats for analysis\n"
            f"From {since.isoformat() if since else 'the beginning'} to {timezone.now().isoformat()}\n"
            f"Model now: {settings.DESIGN3D_MODEL}\n\n"
            "One folder per design with new messages: chat.txt (the chat as read by a person), design.json (every turn "
            "with its model, tokens, cost, steps and pictures; every version with its findings), vN.scad (each version's "
            "code), pictures/ (what people sent). Turns marked \"new\": true arrived since the last send.\n\n"
            + json.dumps(counts, indent=1)))
    return out.getvalue(), counts


def token(export):
    return signing.dumps({"x": export.pk}, salt=SALT)


def from_token(value):
    try:
        data = signing.loads(value, salt=SALT, max_age=HOURS * 3600)
    except signing.BadSignature:
        return None
    return Export.objects.filter(pk=data.get("x")).first()


def send(request):
    """Build, keep and mail one export. Returns the Export."""
    cfg = Settings.get()
    since = cfg.last_export_at
    now = timezone.now()
    data, counts = build(since)
    export = Export(since=since, designs=counts["designs"], messages=counts["messages"], pictures=counts["pictures"])
    export.file.save("design3d.zip", ContentFile(data), save=False)
    export.save()
    link = request.build_absolute_uri(f"/design3d/x/a/{token(export)}/")
    body = (f"design3d chats for analysis: {counts['designs']} designs, {counts['messages']} new messages, "
            f"{counts['pictures']} pictures, ${counts['cost_usd']} of model calls.\n"
            f"Since {since:%d %b %Y %H:%M} " if since else
            f"design3d chats for analysis: {counts['designs']} designs, {counts['messages']} messages, "
            f"{counts['pictures']} pictures, ${counts['cost_usd']} of model calls.\nFrom the beginning ")
    body += f"to {timezone.localtime(now):%d %b %Y %H:%M}.\n\nThe zip, for a day: {link}\n"
    msg = EmailMessage(f"design3d chats for analysis, {timezone.localtime(now):%d %b %Y}", body,
                       settings.DEFAULT_FROM_EMAIL, TO)
    if len(data) <= MAX_ATTACH:
        msg.attach(f"design3d-analysis-{now:%Y%m%d-%H%M}.zip", data, "application/zip")
    else:
        msg.body += "\nToo big to attach: use the link.\n"
    try:
        export.sent = bool(msg.send())
    except Exception:
        log.exception("design3d: the analysis mail failed")
        export.sent = False
    export.save(update_fields=["sent"])
    cfg.last_export_at = now
    cfg.save(update_fields=["last_export_at"])
    return export
