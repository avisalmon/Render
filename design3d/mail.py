"""The one email design3d sends: you are in (REQ-D3.3). Sent once per
person, and "sent" only when the mail backend said so (methodology 53)."""

import logging

from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone

log = logging.getLogger(__name__)


def welcome(maker, request=None):
    if maker.welcomed_at or not maker.user.email:
        return False
    link = request.build_absolute_uri("/design3d/") if request else "https://babook.co.il/design3d/"
    body = (
        f"Hi {maker.display_name},\n\n"
        "You are in design3d: describe a part, send a sketch or a photo, and get a printable STL.\n"
        f"{link}\n\n"
        "Sign in with the same account you asked with.\n\n"
        "Avi Salmon"
    )
    try:
        sent = send_mail("You are in design3d", body, settings.DEFAULT_FROM_EMAIL, [maker.user.email])
    except Exception:
        log.exception("design3d: the welcome email to %s failed", maker.user.email)
        return False
    if not sent:
        return False
    maker.welcomed_at = timezone.now()
    maker.save(update_fields=["welcomed_at"])
    return True


# ---------- "Email me this chat" (Avi, 2026-10-29) ----------

EXPORT_LIMIT = 15 * 1024 * 1024  # bytes of attachments: Gmail takes 25 MB, base64 adds a third


def _version_line(v):
    if v is None:
        return ""
    bits = [f"version {v.number}", v.made_by, v.status]
    if v.size_mm:
        bits.append(f"{v.size_mm} mm")
    if v.build_seconds is not None:
        bits.append(f"built in {v.build_seconds} s")
    if v.print_summary:
        bits.append(v.print_summary)
    line = " · ".join(bits)
    if v.error:
        line += "\n      error: " + v.error.splitlines()[0][:300]
    return line


def chat_text(design):
    """The whole chat as plain text: every message, the model, the cost, the
    assumptions, how each turn went and what it built."""
    from . import builder

    out = [f"design3d chat #{design.pk}: {design.title}",
           f"Owner: {design.owner.display_name} · created {timezone.localtime(design.created_at):%Y-%m-%d %H:%M}",
           f"Model now: {settings.DESIGN3D_MODEL} · engine: OpenSCAD {builder.engine() or 'not installed'}"
           f"{' (Manifold)' if builder.manifold() else ''}",
           f"Current version: {design.current.number if design.current else 'none'}", ""]
    total = 0
    for m in design.messages.prefetch_related("pictures").select_related("version"):
        when = f"{timezone.localtime(m.created_at):%H:%M:%S}"
        if m.role == m.PERSON:
            out.append(f"[{when}] PERSON")
        else:
            total += m.cost_usd
            out.append(f"[{when}] DESIGN3D ({m.model or '-'}, ${m.cost_usd}, tokens in {m.tokens_in} "
                       f"cached {m.tokens_cached} out {m.tokens_out}, {m.state})")
        out.append("  " + (m.text or "").replace("\n", "\n  "))
        for a in m.assumptions or []:
            out.append(f"  assumed: {a}")
        for n, p in enumerate(m.pictures.all(), 1):
            out.append(f"  picture: msg{m.pk}-{n}.jpg ({p.width} x {p.height})")
        if m.version_id:
            out.append("  -> " + _version_line(m.version))
        for seconds, what in m.trail or []:
            out.append(f"     {seconds:>4} s  {what}")
        out.append("")
    out.append(f"Model cost of this chat: ${total}")
    out += ["", "VERSIONS"]
    for v in design.versions.order_by("number"):
        out.append("  " + _version_line(v))
        for c in v.checks or []:
            out.append(f"      {c['level']}: {c['text']}")
    return "\n".join(out)


EXPORT_SALT = "design3d-export"
EXPORT_HOURS = 24


def export_token(design):
    from django.core import signing

    return signing.dumps({"d": design.pk}, salt=EXPORT_SALT)


def export_design(token):
    """The design a link points to, or None when it is wrong or older than a day."""
    from django.core import signing

    from .models import Design

    try:
        data = signing.loads(token, salt=EXPORT_SALT, max_age=EXPORT_HOURS * 3600)
    except signing.BadSignature:
        return None
    return Design.objects.filter(pk=data.get("d")).first()


def email_chat(design, to, base_url="https://babook.co.il"):
    """Send the chat to `to` with the pictures, every version's code, the
    previews and the current STL. True when the backend took it.

    The body also carries every version's code and a private link, good for
    a day, to a page with the pictures: Claude reads the mail through a
    Gmail connection that cannot open attachments (Avi, 2026-10-29)."""
    from django.core.mail import EmailMessage

    body = chat_text(design)
    body += f"\n\nPictures and previews, for a day: {base_url}/design3d/x/{export_token(design)}/\n"
    for v in design.versions.order_by("number"):
        body += f"\n----- v{v.number}.scad -----\n{v.code}\n"
    msg = EmailMessage(f"design3d chat #{design.pk}: {design.title}", body, settings.DEFAULT_FROM_EMAIL, [to])
    used, skipped = 0, []

    def attach(name, data, kind):
        nonlocal used
        if used + len(data) > EXPORT_LIMIT:
            skipped.append(name)
            return
        used += len(data)
        msg.attach(name, data, kind)

    msg.attach(f"design3d-{design.pk}-chat.txt", body.encode("utf-8"), "text/plain")
    for v in design.versions.order_by("number"):
        attach(f"v{v.number}.scad", v.code.encode("utf-8"), "text/plain")
    for m in design.messages.prefetch_related("pictures"):
        for n, p in enumerate(m.pictures.all(), 1):
            try:
                with p.image.open("rb") as fh:
                    attach(f"msg{m.pk}-{n}.jpg", fh.read(), "image/jpeg")
            except OSError:
                skipped.append(f"msg{m.pk}-{n}.jpg (missing)")
    for v in design.versions.filter(status="ready").order_by("number"):
        if v.preview:
            try:
                with v.preview.open("rb") as fh:
                    attach(f"v{v.number}.png", fh.read(), "image/png")
            except OSError:
                skipped.append(f"v{v.number}.png (missing)")
    if design.current and design.current.stl:
        try:
            with design.current.stl.open("rb") as fh:
                attach(f"v{design.current.number}.stl", fh.read(), "model/stl")
        except OSError:
            skipped.append(f"v{design.current.number}.stl (missing)")
    if skipped:
        msg.body += "\n\nNot attached (too big or missing): " + ", ".join(skipped)
    try:
        return bool(msg.send())
    except Exception:
        log.exception("design3d: emailing chat %s failed", design.pk)
        return False


def send_files(design, to):
    """The current part's STL and OpenSCAD code to the owner's own address
    (the Done page's Send). True when the backend took it."""
    from django.core.mail import EmailMessage

    v = design.current
    body = (f"{design.title}, version {v.number}" + (f", {v.size_mm} mm" if v.size_mm else "") + ".\n\n"
            "The STL is ready for your slicer; the .scad file opens in OpenSCAD.\n\n"
            f"https://babook.co.il/design3d/d/{design.pk}/\n")
    msg = EmailMessage(f"{design.title}: your design3d files", body, settings.DEFAULT_FROM_EMAIL, [to])
    name = "".join(c if c.isalnum() else "-" for c in design.title.lower()).strip("-") or "part"
    try:
        with v.stl.open("rb") as fh:
            msg.attach(f"{name}-v{v.number}.stl", fh.read(), "model/stl")
    except (OSError, ValueError):
        return False
    msg.attach(f"{name}-v{v.number}.scad", v.code.encode("utf-8"), "text/plain")
    try:
        return bool(msg.send())
    except Exception:
        log.exception("design3d: sending the files of %s failed", design.pk)
        return False


# ---------- asking and inviting (Avi, 2026-10-29) ----------

def _admins():
    from django.contrib.auth import get_user_model

    from .models import Maker

    emails = set(get_user_model().objects.filter(is_superuser=True, is_active=True).exclude(email="").values_list("email", flat=True))
    emails |= set(Maker.objects.filter(is_admin=True).exclude(user__email="").values_list("user__email", flat=True))
    return sorted(emails)


def request_notice(maker, request=None):
    """Tell Avi that someone asked to come in. True when the backend took it."""
    to = _admins()
    if not to:
        return False
    link = request.build_absolute_uri("/design3d/people/") if request else "https://babook.co.il/design3d/people/"
    body = (f"{maker.display_name} ({maker.user.email or 'no email'}) asked to join design3d.\n\n"
            + (f"Why: {maker.reason}\n\n" if maker.reason else "")
            + f"Approve or decline: {link}\n")
    try:
        return bool(send_mail(f"design3d: {maker.display_name} asks to join", body, settings.DEFAULT_FROM_EMAIL, to))
    except Exception:
        log.exception("design3d: the request notice for %s failed", maker.pk)
        return False


def invite(inv, request=None):
    """The invitation: one link with a one-time key. True when the backend took it."""
    link = (request.build_absolute_uri(f"/design3d/i/{inv.token}/") if request
            else f"https://babook.co.il/design3d/i/{inv.token}/")
    hello = f"Hi {inv.name},\n\n" if inv.name else "Hi,\n\n"
    body = (hello
            + "Avi Salmon invites you to design3d: describe a part, send a sketch or a photo, and get a printable STL.\n\n"
            + f"Your invitation: {link}\n\n"
            + "Open it and sign in (Google, or an email and password). The link works once, for one person, "
            + f"and ends on {timezone.localtime(inv.expires_at):%d %B %Y}.\n\n"
            + "Avi Salmon")
    try:
        return bool(send_mail("You are invited to design3d", body, settings.DEFAULT_FROM_EMAIL, [inv.email]))
    except Exception:
        log.exception("design3d: the invite to %s failed", inv.email)
        return False
