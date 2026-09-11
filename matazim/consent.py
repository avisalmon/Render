"""Whether a parent has said yes, and what happens while they have not.

REQ-M.84, spec §4.10 finding P4. The programme is ninth-graders, so the consent
of the person typing is not on its own the consent the law is looking for.

Two decisions are worth reading before changing anything here.

**A blank birth year is not an adult.** Everyone who registered before this
shipped has one. Reading blank as "adult" would exempt the entire existing
population in a way nobody would ever notice, which is the worst property a
safety check can have. Blank means we have to ask.

**The gate is on joining a leader, not on the account.** This is the part that
took the most thought. A consent requirement arriving after people have already
started is a retrofit, and a retrofit in front of the account would lock a
teenager out of work they have already done, for a rule that did not exist when
they did it. So it sits at the moment their data starts being shown to another
person, which is exactly the moment consent is actually owed, and not one screen
earlier. They can sign in, do the entrance test, and see their own progress with
no parent involved at all, because none of that is disclosed to anyone.
"""

from django.utils import timezone

ADULT_AT = 18


def age_now(profile):
    """Approximate, on purpose: we hold the year and nothing finer (REQ-M.84).

    Off by up to one depending on their birthday, which is the correct trade.
    Storing a full date of birth would buy exactness we have no use for, in
    exchange for holding more about a child.
    """
    if profile is None or not profile.birth_year:
        return None
    return timezone.now().year - profile.birth_year


def is_minor(profile):
    """Unknown counts as a minor. See the note at the top of this file."""
    age = age_now(profile)
    if age is None:
        return True
    return age < ADULT_AT


def has_guardian_consent(profile):
    return bool(profile and profile.guardian_consent_at)


def needs_guardian_consent(profile):
    """The one question every caller asks."""
    if profile is None:
        return True
    return is_minor(profile) and not has_guardian_consent(profile)


def record_guardian_consent(profile, *, name="", email="", recorded_by=None):
    """Write it down, with who said so.

    `recorded_by` is the admin entering consent a school collected on paper, and
    stays null when the consent was given here at registration. A school having
    collected it is not the same fact as a parent having typed it, and somebody
    will eventually need to tell them apart.
    """
    profile.guardian_name = name or profile.guardian_name
    profile.guardian_email = email or profile.guardian_email
    profile.guardian_consent_at = timezone.now()
    profile.guardian_consent_recorded_by = recorded_by
    profile.save(
        update_fields=[
            "guardian_name",
            "guardian_email",
            "guardian_consent_at",
            "guardian_consent_recorded_by",
            "updated_at",
        ]
    )
    return profile


def consent_blocker(profile):
    """Why they cannot join yet, in words, or None if they can.

    Same principle as REQ-M.77: a refusal that does not say why reads as a
    broken site, and a teenager who thinks the site is broken stops.
    """
    if not needs_guardian_consent(profile):
        return None
    if not (profile and profile.birth_year):
        return "עוד לא אמרתם לנו באיזו שנה נולדתם, וזה מה שקובע אם צריך אישור הורה."
    return "כדי להצטרף למוביל/ה צריך אישור של הורה או אפוטרופוס."
