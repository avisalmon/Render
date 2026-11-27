"""Every path that gives a person access, in one place (spec 2.2, 2.4, 2.6,
4.5; methodology 53 and 55).

A role is granted, revoked, marked or requested here and nowhere else: the
admin's screens, the agent's API endpoint, the CLI and the invitation link
all call these functions. Each one writes the rows, logs the change in the
ChangeLog, and sends the one mail through `mail.send`; what it returns
carries the backend's own count, so a screen says "sent" only when a mail
really left.

Nothing here creates an account except `redeem`, which does so only for the
address an invitation was sent to (the invitation is the verification), and
never touches staff, superuser or password of an existing account.
"""

from dataclasses import dataclass, field

from django.contrib.auth import get_user_model
from django.db import models as dj_models
from django.db import transaction
from django.urls import reverse
from django.utils import timezone
from django.utils.crypto import get_random_string

from . import mail
from .models import (
    ChangeLog,
    CommitteeAttribute,
    Invitation,
    LeaderOf,
    Program,
    Role,
    RoleRequest,
)

INVITATION_DAYS = 14

ROLE_WORDS = dict(Role.KINDS)
ATTRIBUTE_WORDS = dict(CommitteeAttribute.KINDS)
HOME = "/academia360/"


@dataclass
class Done:
    """What happened, for a screen or an API answer."""

    ok: bool
    what: str
    mailed: object = 0  # the backend's count; None when there was nothing to send
    row: object = None
    status: int = 200
    extra: dict = field(default_factory=dict)

    @property
    def mail_word(self):
        if self.mailed is None:
            return ""
        return "המייל נשלח" if self.mailed else "המייל לא נשלח"


# ------------------------------------------------------------------ helpers

def _text(value):
    if value is None:
        return ""
    if hasattr(value, "pk"):
        return str(value.pk)
    return str(value)


def _snapshot(instance):
    return {f.name: _text(getattr(instance, f.attname if isinstance(f, dj_models.ForeignKey) else f.name))
            for f in instance._meta.concrete_fields if f.name not in ("id", "created_at", "updated_at")}


def _log(actor, instance, before=None, deleted=False, agent=False, reason=""):
    kind = ChangeLog.AGENT if agent else ChangeLog.PERSON
    by = actor if getattr(actor, "is_authenticated", False) else None
    common = dict(model=instance._meta.label, row_id=str(instance.pk), by=by, actor_kind=kind, reason=reason[:300])
    if deleted:
        ChangeLog.objects.create(field="", old="deleted", new="", **common)
    elif before is None:
        ChangeLog.objects.create(field="", old="", new="created", **common)
    else:
        after = _snapshot(instance)
        rows = [ChangeLog(field=k, old=before[k], new=after[k], **common) for k in after if after[k] != before.get(k)]
        ChangeLog.objects.bulk_create(rows)


def _name(user):
    return (user.get_full_name() or "").strip() or user.email or user.get_username()


def _program():
    return Program.objects.order_by("pk").first()


def find_account(email):
    """An existing account by email (or username). Never creates one."""
    User = get_user_model()
    email = (email or "").strip()
    if not email:
        return None
    return (User.objects.filter(email__iexact=email).order_by("pk").first()
            or User.objects.filter(username__iexact=email).first())


def role_sentence(user):
    """What this person is in the app, in one line, for /me/ and the admin."""
    held = list(Role.objects.filter(user=user, active=True).values_list("kind", flat=True))
    if getattr(user, "is_superuser", False) and Role.ADMIN not in held:
        held.insert(0, Role.ADMIN)
    parts = []
    for kind in (Role.ADMIN, Role.COMMITTEE_MEMBER, Role.LEADER):
        if kind not in held:
            continue
        if kind == Role.LEADER:
            insts = [lead.institution.short_name_he or lead.institution.name_he
                     for lead in LeaderOf.objects.filter(user=user, active=True).select_related("institution")]
            parts.append(f"{ROLE_WORDS[kind]}: {', '.join(insts)}" if insts else ROLE_WORDS[kind])
        elif kind == Role.COMMITTEE_MEMBER:
            marks = []
            if CommitteeAttribute.objects.filter(user=user, kind=CommitteeAttribute.CHAIR).exists():
                marks.append(ATTRIBUTE_WORDS[CommitteeAttribute.CHAIR])
            reviewed = [a.institution.short_name_he or a.institution.name_he for a in
                        CommitteeAttribute.objects.filter(user=user, kind=CommitteeAttribute.REVIEWER,
                                                          institution__isnull=False).select_related("institution")]
            if reviewed:
                marks.append("סוקר/ת של " + ", ".join(reviewed))
            parts.append(ROLE_WORDS[kind] + (f" ({'; '.join(marks)})" if marks else ""))
        else:
            parts.append(ROLE_WORDS[kind])
    return " · ".join(parts)


# -------------------------------------------------------------------- roles

def grant_role(actor, user, kind, institution=None, title="", agent=False, base=None, reason=""):
    """Grant a role (reactivating a revoked one). A leader needs an
    institution and gets a LeaderOf row; the person is mailed."""
    if kind not in ROLE_WORDS:
        return Done(False, "אין תפקיד כזה.", status=400)
    if kind == Role.LEADER and institution is None:
        return Done(False, "מוביל תכנית צריך מוסד.", status=400)
    changed = False
    with transaction.atomic():
        role = Role.objects.filter(user=user, kind=kind).first()
        if role is None:
            role = Role.objects.create(user=user, kind=kind, granted_by=actor if getattr(actor, "pk", None) else None)
            _log(actor, role, agent=agent, reason=reason)
            changed = True
        elif not role.active:
            before = _snapshot(role)
            role.active = True
            role.granted_by = actor if getattr(actor, "pk", None) else None
            role.save(update_fields=["active", "granted_by"])
            _log(actor, role, before=before, agent=agent, reason=reason)
            changed = True
        if kind == Role.LEADER:
            lead, created = LeaderOf.objects.get_or_create(user=user, institution=institution,
                                                           defaults={"title": title, "active": True})
            if created:
                _log(actor, lead, agent=agent, reason=reason)
                changed = True
            elif not lead.active or (title and lead.title != title):
                before = _snapshot(lead)
                lead.active, lead.title = True, title or lead.title
                lead.save(update_fields=["active", "title"])
                _log(actor, lead, before=before, agent=agent, reason=reason)
                changed = True
    what = ROLE_WORDS[kind]
    if institution is not None and kind == Role.LEADER:
        what += f" ב{institution.short_name_he or institution.name_he}"
    if not changed:
        return Done(True, f"{_name(user)} כבר {what}.", mailed=None, row=role)
    base = base or mail.base_url()
    mailed = mail.send(
        f"קיבלתם תפקיד: {what}",
        f"שלום {_name(user)},\n\nבאקדמיה 360° נפתח לכם תפקיד: {what}.\n"
        f"נכנסים עם החשבון שלכם ({user.email}) כאן:\n{base}{HOME}\n",
        user.email)
    return Done(True, f"{_name(user)} עכשיו {what}.", mailed=mailed, row=role)


def revoke_role(actor, user, kind, institution=None, agent=False, reason=""):
    """Take a role away. Revoking a leader of one institution leaves the role
    when they still lead another. The account itself is never touched."""
    if kind not in ROLE_WORDS:
        return Done(False, "אין תפקיד כזה.", status=400)
    changed = False
    with transaction.atomic():
        if kind == Role.LEADER and institution is not None:
            for lead in LeaderOf.objects.filter(user=user, institution=institution, active=True):
                before = _snapshot(lead)
                lead.active = False
                lead.save(update_fields=["active"])
                _log(actor, lead, before=before, agent=agent, reason=reason)
                changed = True
            if LeaderOf.objects.filter(user=user, active=True).exists():
                return Done(True, f"{_name(user)} כבר לא מוביל/ה ב{institution.short_name_he or institution.name_he}; "
                                  f"התפקיד נשאר למוסדות האחרים.", mailed=None)
        elif kind == Role.LEADER:
            for lead in LeaderOf.objects.filter(user=user, active=True):
                before = _snapshot(lead)
                lead.active = False
                lead.save(update_fields=["active"])
                _log(actor, lead, before=before, agent=agent, reason=reason)
                changed = True
        role = Role.objects.filter(user=user, kind=kind, active=True).first()
        if role is not None:
            before = _snapshot(role)
            role.active = False
            role.save(update_fields=["active"])
            _log(actor, role, before=before, agent=agent, reason=reason)
            changed = True
            if kind == Role.COMMITTEE_MEMBER:
                for attr in CommitteeAttribute.objects.filter(user=user):
                    _log(actor, attr, deleted=True, agent=agent, reason=reason)
                    attr.delete()
    if not changed:
        return Done(True, f"{_name(user)} לא היה/תה {ROLE_WORDS[kind]}.", mailed=None)
    mailed = mail.send(f"התפקיד הוסר: {ROLE_WORDS[kind]}",
                       f"שלום {_name(user)},\n\nהתפקיד {ROLE_WORDS[kind]} באקדמיה 360° הוסר מהחשבון שלכם. "
                       f"החשבון עצמו נשאר כמו שהיה.\n", user.email)
    return Done(True, f"{_name(user)} כבר לא {ROLE_WORDS[kind]}.", mailed=mailed)


def set_attribute(actor, user, kind, institution=None, agent=False, reason=""):
    """Mark a committee member as chair, or as reviewer of an institution."""
    if kind not in ATTRIBUTE_WORDS:
        return Done(False, "אין סימון כזה.", status=400)
    if not Role.objects.filter(user=user, kind=Role.COMMITTEE_MEMBER, active=True).exists():
        return Done(False, "סימון יושב על חבר/ת ועדה; תנו קודם את תפקיד הוועדה.", status=400)
    if kind == CommitteeAttribute.REVIEWER and institution is None:
        return Done(False, "סוקר/ת צריך/ה מוסד.", status=400)
    program = _program()
    if program is None:
        return Done(False, "עוד אין תכנית.", status=400)
    keys = dict(user=user, kind=kind, program=program, institution=institution if kind == CommitteeAttribute.REVIEWER else None)
    attr, created = CommitteeAttribute.objects.get_or_create(**keys)
    word = ATTRIBUTE_WORDS[kind] + (f" של {institution.short_name_he or institution.name_he}" if institution is not None
                                    and kind == CommitteeAttribute.REVIEWER else "")
    if not created:
        return Done(True, f"{_name(user)} כבר {word}.", mailed=None, row=attr)
    _log(actor, attr, agent=agent, reason=reason)
    mailed = mail.send(f"סומנתם: {word}",
                       f"שלום {_name(user)},\n\nבאקדמיה 360° סומנתם כ{word}.\n{mail.base_url()}{HOME}\n", user.email)
    return Done(True, f"{_name(user)} עכשיו {word}.", mailed=mailed, row=attr)


def clear_attribute(actor, user, kind, institution=None, agent=False, reason=""):
    if kind not in ATTRIBUTE_WORDS:
        return Done(False, "אין סימון כזה.", status=400)
    rows = CommitteeAttribute.objects.filter(user=user, kind=kind)
    if kind == CommitteeAttribute.REVIEWER and institution is not None:
        rows = rows.filter(institution=institution)
    n = 0
    for attr in rows:
        _log(actor, attr, deleted=True, agent=agent, reason=reason)
        attr.delete()
        n += 1
    if not n:
        return Done(True, f"{_name(user)} לא היה/תה {ATTRIBUTE_WORDS[kind]}.", mailed=None)
    return Done(True, f"הסימון {ATTRIBUTE_WORDS[kind]} הוסר מ{_name(user)}.", mailed=None)


# -------------------------------------------------------- asking to join

REQUEST_KINDS = dict(RoleRequest._meta.get_field("role_kind").choices)


def ask_to_join(user, kind, institution=None, title="", message="", base=None):
    """A signed-in person asks for a role. One open request per kind; a
    person who already holds the role is told so. The admins are mailed."""
    if kind not in REQUEST_KINDS:
        return Done(False, "אין תפקיד כזה.", status=400)
    if kind == Role.LEADER and institution is None:
        return Done(False, "איזה מוסד? מוביל תכנית שייך למוסד אחד.", status=400)
    if Role.objects.filter(user=user, kind=kind, active=True).exists():
        return Done(False, f"כבר יש לכם תפקיד {REQUEST_KINDS[kind]}.", status=409)
    if RoleRequest.objects.filter(user=user, role_kind=kind, status="open").exists():
        return Done(False, f"כבר יש בקשה פתוחה שלכם להיות {REQUEST_KINDS[kind]}; היא מחכה למנהל המערכת.", status=409)
    row = RoleRequest.objects.create(user=user, role_kind=kind, institution=institution if kind == Role.LEADER else None,
                                     title=(title or "")[:160], message=(message or "")[:2000])
    _log(user, row)
    mailed = announce_request(row, base=base)
    return Done(True, "הבקשה נשלחה למנהל המערכת. תקבלו מייל כשתוכרע, והמצב מופיע בעמוד 'שלי'.", mailed=mailed, row=row)


def announce_request(row, base=None):
    """Tell the admins a request landed (also used when one arrives through
    the generic API)."""
    base = base or mail.base_url()
    inst = f"\nמוסד: {row.institution.name_he}" if row.institution_id else ""
    title = f"\nתפקיד במוסד: {row.title}" if row.title else ""
    body = (f"{_name(row.user)} ({row.user.email}) מבקש/ת להיות {REQUEST_KINDS.get(row.role_kind, row.role_kind)}."
            f"{inst}{title}\n\n{row.message or '(בלי הודעה)'}\n\nלתור הבקשות:\n{base}{reverse('academia360:manage_people')}\n")
    return mail.send(f"בקשה להצטרף: {_name(row.user)}", body, mail.admin_emails())


def decide_request(actor, row, approve, note="", agent=False, base=None):
    """Approve (the role is granted and the person mailed) or decline with a
    word (the person is mailed the word). Only an open request is decided."""
    if row.status != "open":
        return Done(False, "הבקשה כבר הוכרעה.", status=409)
    base = base or mail.base_url()
    with transaction.atomic():
        before = _snapshot(row)
        if approve:
            if row.role_kind == Role.LEADER and row.institution_id is None:
                return Done(False, "הבקשה בלי מוסד; אי אפשר לאשר מוביל בלי מוסד.", status=400)
            granted = grant_role(actor, row.user, row.role_kind, institution=row.institution, title=row.title,
                                 agent=agent, base=base, reason="request approved")
            if not granted.ok:
                return granted
            row.status = "approved"
        else:
            row.status = "declined"
        row.decided_by = actor if getattr(actor, "pk", None) else None
        row.decided_at = timezone.now()
        row.decision_note = (note or "")[:300]
        row.save(update_fields=["status", "decided_by", "decided_at", "decision_note"])
        _log(actor, row, before=before, agent=agent)
    if approve:
        return Done(True, f"אושר: {granted.what}", mailed=granted.mailed, row=row)
    mailed = mail.send("הבקשה להצטרף לא אושרה",
                       f"שלום {_name(row.user)},\n\nהבקשה שלכם להיות {REQUEST_KINDS.get(row.role_kind, row.role_kind)} "
                       f"באקדמיה 360° לא אושרה.{(chr(10) + chr(10) + note) if note else ''}\n", row.user.email)
    return Done(True, f"נדחה: {_name(row.user)}.", mailed=mailed, row=row)


# ------------------------------------------------------------- invitations

def invite(actor, email, kind, institution=None, title="", agent=False, base=None, reason=""):
    """Invite an address that has no account yet: an Invitation with a token,
    mailed with its link. An address that already has an account is granted
    directly instead (no need for a door it already has)."""
    email = (email or "").strip().lower()
    if "@" not in email:
        return Done(False, "צריך כתובת מייל.", status=400)
    if kind not in ROLE_WORDS:
        return Done(False, "אין תפקיד כזה.", status=400)
    if kind == Role.LEADER and institution is None:
        return Done(False, "מוביל תכנית צריך מוסד.", status=400)
    existing = find_account(email)
    if existing is not None:
        done = grant_role(actor, existing, kind, institution=institution, title=title, agent=agent, base=base, reason=reason)
        done.extra["existing_account"] = True
        return done
    base = base or mail.base_url()
    row = Invitation.objects.create(email=email, role_kind=kind, institution=institution if kind == Role.LEADER else None,
                                    title=(title or "")[:160], token=get_random_string(48),
                                    sent_by=actor if getattr(actor, "pk", None) else None)
    _log(actor, row, agent=agent, reason=reason)
    mailed = resend_invitation(row, base=base)
    word = ROLE_WORDS[kind] + (f" ב{institution.short_name_he or institution.name_he}" if institution is not None and kind == Role.LEADER else "")
    return Done(True, f"הזמנה ל{email} להיות {word}.", mailed=mailed, row=row)


def invitation_link(row, base=None):
    return f"{base or mail.base_url()}{reverse('academia360:invite', args=[row.token])}"


def resend_invitation(row, base=None):
    """Mail (again) the link of an open invitation; `sent_at` records the
    last time the backend accepted it."""
    if row.accepted_at is not None:
        return 0
    word = ROLE_WORDS.get(row.role_kind, row.role_kind)
    if row.institution_id and row.role_kind == Role.LEADER:
        word += f" ב{row.institution.short_name_he or row.institution.name_he}"
    mailed = mail.send(f"הזמנה: {word}",
                       f"שלום,\n\nהוזמנתם לאקדמיה 360° בתפקיד {word}.\nהקישור הזה פותח לכם את הגישה "
                       f"(תקף {INVITATION_DAYS} ימים, לכתובת {row.email}):\n{invitation_link(row, base)}\n", row.email)
    if mailed:
        row.sent_at = timezone.now()
        row.save(update_fields=["sent_at"])
    return mailed


def invitation_state(row):
    """`open`, `accepted` or `expired`."""
    if row.accepted_at is not None:
        return "accepted"
    since = row.sent_at or row.created_at
    if since is None or timezone.now() - since > timezone.timedelta(days=INVITATION_DAYS):
        return "expired"
    return "open"


def redeem(user, row, base=None):
    """The signed-in holder of a link gets the role. Ownership first: the
    person who already redeemed it may open it again (a no-op success);
    anyone else after that is refused; then validity (methodology 55)."""
    if row.accepted_at is not None:
        if row.accepted_by_id == user.pk:
            return Done(True, "ההזמנה הזאת כבר שלכם; הגישה פתוחה.", mailed=None, row=row)
        return Done(False, "ההזמנה הזאת כבר נוצלה על ידי מישהו אחר.", status=403)
    if invitation_state(row) == "expired":
        return Done(False, f"ההזמנה פגה (היא תקפה {INVITATION_DAYS} ימים). בקשו הזמנה חדשה.", status=410)
    with transaction.atomic():
        before = _snapshot(row)
        granted = grant_role(row.sent_by, user, row.role_kind, institution=row.institution, title=row.title,
                             base=base, reason="invitation redeemed")
        if not granted.ok:
            return granted
        row.accepted_at = timezone.now()
        row.accepted_by = user
        row.save(update_fields=["accepted_at", "accepted_by"])
        _log(user, row, before=before)
    told = mail.send(f"הזמנה נוצלה: {_name(user)}",
                     f"{_name(user)} ({user.email}) פתח/ה את ההזמנה ל{row.email} וקיבל/ה: {granted.what}\n",
                     mail.admin_emails())
    return Done(True, granted.what, mailed=granted.mailed, row=row, extra={"admins_told": told})


def make_account_for(row, password):
    """An account for the invited address, only from an open invitation. No
    flags, the email fixed to the invited one (the invitation verified it).
    Returns the user, or None when the address already has an account."""
    User = get_user_model()
    if find_account(row.email) is not None:
        return None
    username = row.email
    if User.objects.filter(username=username).exists():
        username = f"{row.email}-{get_random_string(6).lower()}"
    return User.objects.create_user(username, row.email, password)
