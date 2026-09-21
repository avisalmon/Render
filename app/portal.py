"""Which apps a person has, and the one place that decides it.

`main_spec.md` §0.5, REQ-13.1. Avi answered ACT-27 on 2026-09-21 by listing the
apps and their audiences: memz everyone, מט״צים everyone, SensorLab everyone,
ustrip the family, the house him alone.

**Why one function instead of a list on the home page.** The portal and each
app's own door are two places asking the same question, and two answers drift.
The drift is invisible in exactly the way that costs something: a card that
refuses when clicked, or a hidden card whose URL still opens. This repo has
made that mistake twice and fixed it twice the same way, by making one function
the only place the question is answered (REQ-M.144 for tenancy,
`visible_course_slugs` for courses). So `visible_apps` and `may_enter` are the
same decision seen from two sides, and a sweep in `test_spr_13_1.py` asks both
about every app for every kind of person and fails if they ever differ.

**Three kinds of audience, because that is what the answer contained**, and all
three already existed in the code before this module did:

- `EVERYONE` — every signed-in person. It says nothing about what they see
  *inside*: מט״צים is open to everyone and still shows a stranger its front
  door rather than a member's screens.
- `GROUP` — membership of a Django group. ustrip has used `family` since it
  was built.
- `PEOPLE` — a named list, read from settings rather than written here, so
  changing who may see the house is a deploy setting and not a code change.

**Nothing here imports an app.** babook may not depend on the things that
depend on it, so the rules are expressed in babook's own terms: a group name, a
settings key. An app's door is welcome to ask this module; this module asks no
app anything.

**Staff get no bypass, on purpose.** A superuser can already reach any row
through /admin/, so a bypass here buys nothing, and the two rules that are not
"everyone" are the two that are actually about privacy: a family's trip and one
household's cameras. Fail shut and let the list decide.
"""

from dataclasses import dataclass

from django.conf import settings

EVERYONE = "everyone"
GROUP = "group"
PEOPLE = "people"


@dataclass(frozen=True)
class App:
    """One app, as the portal needs to know it.

    `name` and `blurb` are what a person reads on the card. Deliberately short:
    this is a directory, and anything longer belongs in the app's own docs.
    """

    slug: str
    name: str
    path: str
    audience: str
    blurb: str
    key: str = ""  # the group name, or the settings key holding the list
    admin_bypass: bool = False  # see below; only ustrip declares it


APPS = [
    App(
        slug="matazim",
        name="מט״צים",
        path="/matazim/",
        audience=EVERYONE,
        blurb="תוכנית מנהיגות טכנולוגית צעירה: לומדים, יוצרים, מדריכים ומוסמכים.",
    ),
    App(
        slug="sensorlab",
        name="SensorLab",
        path="/sensorlab/",
        audience=EVERYONE,
        blurb="מעבדת פיזיקה בטלפון: החיישנים של המכשיר הם ציוד המעבדה.",
    ),
    App(
        slug="memz",
        name="memz",
        path="/memz/",
        audience=EVERYONE,
        blurb="יוצרים ממים, ומשחקים משחק כתוביות והצבעה עם חברים.",
    ),
    App(
        slug="ustrip",
        name="ustrip",
        path="/ustrip/",
        audience=GROUP,
        key="family",
        # ustrip has let any superuser in since it was built, so the site
        # admin never has to remember to add themself to `family` before
        # opening his own app. Declared here rather than left inside
        # ustrip, because F-13.4 found it as a disagreement: the door
        # opened for an admin and the portal showed them no card.
        admin_bypass=True,
        blurb="תכנון הטיול המשפחתי: התוכנית להיום, הציוד, ויומן התמונות.",
    ),
    App(
        slug="home",
        name="הבית",
        path="/home/",
        audience=PEOPLE,
        key="SECURITY_VIEWER_EMAILS",
        blurb="מה קורה בבית, לקריאה בלבד.",
    ),
]

# Capabilities that exist on the site and are deliberately not on the portal.
# Listed rather than omitted, so that `test_every_installed_app_is_in_the_
# registry_or_deliberately_out` can tell "decided against" from "forgotten".
NOT_IN_THE_PORTAL = {
    # Avi listed five apps on 2026-09-21 and CrashTech was not one of them.
    # Built inside `app/` in 2026-06, before capabilities became apps.
    "crashtech",
}

_BY_SLUG = {a.slug: a for a in APPS}


def _permitted_people(key):
    """The named list for a `PEOPLE` app, read fresh from settings.

    Fresh rather than cached at import, because the list is a deploy setting and
    a cached copy would need a restart to take effect, which is how somebody
    ends up still seeing a page they were removed from.

    The owner address rides along for the house specifically, matching what
    `security_views.permitted_emails` has always done: an empty list means one
    person, not everyone.
    """
    allowed = set(getattr(settings, key, []) or [])
    if key == "SECURITY_VIEWER_EMAILS":
        owner = getattr(settings, "SECURITY_OWNER_EMAIL", "")
        if owner:
            allowed.add(owner)
    return {e.strip().lower() for e in allowed if e and e.strip()}


def _holds_one_of(user, emails):
    """Whether this person holds one of these addresses.

    `User.email` is the usual answer, and it is not the only one: allauth may
    hold a *verified* address that differs from the User row, and somebody the
    owner deliberately added by that address is still that person. The house's
    own door has always read both, and F-13.4 found that the portal read only
    the first, so a person in exactly that position could open `/home` and
    never see a card for it. One rule now, and it is the more careful one.

    Unverified addresses are never enough: an address anybody can type is not
    an identity, and this list is what stands between strangers and a named
    family's cameras.
    """
    if not emails:
        return False
    if (user.email or "").strip().lower() in emails:
        return True
    try:
        from django.db.models.functions import Lower

        return (
            user.emailaddress_set.filter(verified=True)
            .annotate(lowered=Lower("email"))
            .filter(lowered__in=emails)
            .exists()
        )
    except Exception:  # noqa: BLE001 - allauth absent, or its schema differs
        return False


def _may(user, app):
    """The decision itself, for one person and one app.

    Every branch ends in an explicit answer and the function ends in False, so
    an audience kind nobody has implemented yet hides the app rather than
    showing it to everybody.
    """
    if not getattr(user, "is_authenticated", False):
        return False
    if app.admin_bypass and user.is_superuser:
        return True
    if app.audience == EVERYONE:
        return True
    if app.audience == GROUP:
        return user.groups.filter(name=app.key).exists()
    if app.audience == PEOPLE:
        return _holds_one_of(user, _permitted_people(app.key))
    return False


def visible_apps(user):
    """The apps this person has, in registry order. The portal renders these."""
    return [a for a in APPS if _may(user, a)]


def may_enter(user, slug):
    """Whether this person may open that app. An app's own door asks this.

    An unknown slug is False rather than an error: a door asking about
    something that is not in the registry is exactly the case that must not
    open.
    """
    app = _BY_SLUG.get(slug)
    return bool(app and _may(user, app))
