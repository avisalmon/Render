"""Skills: the limits, the start of an upload chat, and publishing a version
(REQ-G.40 to G.62). The AI's part of the chat lives in `skill_chat.py`
(SPR-G.6); this file never calls a model.

Every rule about who may upload what is here, read by the pages and the API
alike, so the two can never disagree.
"""

from django.core.files.base import ContentFile
from django.db import transaction
from django.db.models import F
from django.utils import timezone

from . import scan, skillpack
from .models import ChatMessage, Exhibit, Skill, SkillChat, SkillFile, SkillVersion, Topic

MAX_SKILLS = 2


def published_count(person):
    return Skill.objects.filter(exhibit__owner=person).count()


def may_start(person, skill=None):
    """(allowed, reason key). `skill` is set for an update."""
    if person.skills_blocked_at:
        return False, "skill.blocked"
    from .skill_chat import daily_room

    if not daily_room(person):
        return False, "chat.daily_cap"
    if skill is not None:
        if skill.exhibit.owner_id != person.pk:
            return False, "skill.not_yours"
        if skill.updates_used >= Skill.MAX_UPDATES and not person.admin:
            return False, "skill.no_updates_left"
        return True, ""
    if not person.unlimited_skills and not person.admin and published_count(person) >= MAX_SKILLS:
        return False, "skill.at_limit"
    return True, ""


def open_chat_for(person):
    return SkillChat.objects.filter(person=person, status=SkillChat.OPEN).first()


def say(chat, role, body):
    return ChatMessage.objects.create(chat=chat, role=role, body=body)


def start(person, filename, data, skill=None):
    """Open a chat from an uploaded file. Raises skillpack.Refused when the
    file cannot be a skill (no AI is called for that). Returns (chat, bundle,
    findings)."""
    bundle = skillpack.read_upload(filename, data)
    if skill is not None and bundle.name != skill.name:
        raise skillpack.Refused("skill.update_other_name", bundle.name)
    found = scan.scan(bundle)
    for old in SkillChat.objects.filter(person=person, status=SkillChat.OPEN):
        old.status = SkillChat.ABANDONED
        old.save(update_fields=["status"])
    chat = SkillChat.objects.create(person=person, skill=skill, upload_name=(filename or "")[:200])
    chat.upload.save(f"{person.pk}-{chat.pk}.zip", ContentFile(skillpack.original(bundle)), save=False)
    chat.findings = "\n".join(f.as_text() for f in found)
    chat.save()
    say(chat, ChatMessage.SYSTEM, f"upload {bundle.name}: {len(bundle.files)} files, {bundle.total} bytes, "
                                  f"{len(found)} plain findings")
    return chat, bundle, found


def bundle_of(chat):
    """The bundle a chat is about, read back from what was stored."""
    with chat.upload.open("rb") as fh:
        return skillpack.read_upload("upload.zip", fh.read())


@transaction.atomic
def publish(chat, bundle, title="", blurb="", topics=(), changes_note=""):
    """Turn a checked chat into a published version (REQ-G.54). The caller
    (the skill chat) decides the chat is clean; this only writes rows and
    files. For an update, the old version stays until this one is written."""
    person = chat.person
    skill = chat.skill
    if skill is None:
        card = Exhibit.objects.create(owner=person, kind=Exhibit.SKILL, title=(title or bundle.name)[:120],
                                      blurb=(blurb or bundle.description)[:400], shot_status=Exhibit.OK)
        skill = Skill.objects.create(exhibit=card, name=bundle.name, origin=bundle.origin)
        number = 1
    else:
        card = skill.exhibit
        if blurb:
            card.blurb = blurb[:400]
        card.save()
        number = (skill.versions.order_by("-number").values_list("number", flat=True).first() or 0) + 1
        Skill.objects.filter(pk=skill.pk).update(updates_used=F("updates_used") + 1)
        skill.refresh_from_db()
    if topics:
        card.topics.set(Topic.objects.filter(slug__in=list(topics)))
    version = SkillVersion(skill=skill, number=number, chat=chat, changes_note=changes_note)
    version.upload.save("original.zip", ContentFile(skillpack.original(bundle)), save=False)
    version.package_claude.save("claude-code.zip", ContentFile(skillpack.package(bundle, "claude")), save=False)
    version.package_copilot.save("copilot.zip", ContentFile(skillpack.package(bundle, "copilot")), save=False)
    version.save()
    SkillFile.objects.bulk_create([
        SkillFile(version=version, path=path, size=len(data), sha256=skillpack.sha256(data), text=data.decode("utf-8"))
        for path, data in bundle.files
    ])
    skill.current = version
    skill.save(update_fields=["current"])
    chat.skill, chat.status = skill, SkillChat.PUBLISHED
    chat.ended_at = timezone.now()
    chat.save(update_fields=["skill", "status", "ended_at"])
    return skill


def count_download(skill):
    Skill.objects.filter(pk=skill.pk).update(downloads=F("downloads") + 1)


def remove_files(skill):
    """Before a skill's card is deleted: its files go with it."""
    for v in skill.versions.all():
        for f in (v.upload, v.package_claude, v.package_copilot):
            if f:
                f.delete(save=False)

