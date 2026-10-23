"""Mail for the hand-to-hand flow (Avi, 2026-10-23): every step of a request
and every message in it also reaches the person by email, in their own
language, with a link back to the request. This supersedes the 2026-10-19
"notifications in the app only" decision for deals; friends and the rest
stay in the app.

Sent as background jobs, so no page waits on the mail provider, and never
raised: a mail that fails is logged and the app goes on. The site's mail
guard (app/mail_guard.py) caps mails per recipient per day; a very lively
conversation will have its later mails of the day held, and the messages
are still in the app.
"""

import logging

from django.conf import settings
from django.core.mail import send_mail

from . import jobs
from .models import Message, Notification
from .strings import text as t

log = logging.getLogger(__name__)

MAILED_KINDS_PREFIX = "deal."


def base_url():
    return getattr(settings, "BOOKS_BASE_URL", "https://babook.co.il").rstrip("/")


def deal_link(deal):
    return f"{base_url()}/books/deals/{deal.pk}/"


def _lang(profile):
    return profile.language if profile.language in ("he", "en") else "he"


def notification_text(n, lang):
    """The same words the bell shows, for a deal notification."""
    deal = n.deal
    title = deal.copy.entry.title if deal else (n.entry.title if n.entry_id else "")
    name = deal.other(n.profile).display_name if deal else ""
    date = deal.due_date.strftime("%d.%m.%Y") if deal and deal.due_date else ""
    return t(f"nk.{n.kind}", lang, title=title, name=name, date=date)


def _send(profile, subject, lines, deal):
    email = (profile.user.email or "").strip()
    if not email:
        return False
    lang = _lang(profile)
    body = "\n".join(lines + ["", t("mail.open_request", lang), deal_link(deal), "",
                              t("mail.footer", lang)])
    try:
        send_mail(f"{t('brand', lang)}: {subject}", body, None, [email], fail_silently=False)
        return True
    except Exception:  # noqa: BLE001
        log.exception("books mail failed (deal %s)", deal.pk)
        return False


@jobs.job("mail.notification")
def _notification_job(job):
    n = Notification.objects.filter(pk=job.ref_id).select_related("profile__user", "deal__copy__entry",
                                                                   "deal__owner", "deal__requester").first()
    if n is None or n.deal_id is None:
        return
    lang = _lang(n.profile)
    _send(n.profile, notification_text(n, lang), [t("mail.hello", lang, name=n.profile.display_name), "",
                                                  notification_text(n, lang)], n.deal)


@jobs.job("mail.message")
def _message_job(job):
    m = Message.objects.filter(pk=job.ref_id).select_related("deal__copy__entry", "deal__owner__user",
                                                              "deal__requester__user", "sender").first()
    if m is None:
        return
    to = m.deal.other(m.sender)
    lang = _lang(to)
    title = m.deal.copy.entry.title
    _send(to, t("mail.message_subject", lang, name=m.sender.display_name, title=title),
          [t("mail.hello", lang, name=to.display_name), "",
           t("mail.message_lead", lang, name=m.sender.display_name, title=title), "", m.body], m.deal)


def notify_later(n):
    """Queue the mail for a deal notification; other kinds stay in the app."""
    if n.deal_id is None or not n.kind.startswith(MAILED_KINDS_PREFIX) or n.kind == "deal.message":
        return None  # a message's own mail carries its words (message_later)
    return jobs.enqueue("mail.notification", ref_id=n.pk, profile=n.profile)


def message_later(m):
    return jobs.enqueue("mail.message", ref_id=m.pk, profile=m.sender)

